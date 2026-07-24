-- =============================================================================
-- APPEND-ONLY ENFORCEMENT + DERIVED CURRENCY VIEWS
--
-- Run as the OWNER role, after the Alembic migration that creates the tables.
-- Applied by migration: alembic revision "append_only_enforcement".
--
-- Two layers of defence:
--   1. REVOKE UPDATE/DELETE from the application role.
--   2. A trigger that raises even if privileges are later granted by mistake.
--
-- Layer 2 matters because privileges drift. The trigger does not.
-- =============================================================================

-- Roles are expected to exist already:
--   troy_owner : owns schema, runs migrations
--   troy_app   : the application connects as this

-- -----------------------------------------------------------------------------
-- 1. Privilege revocation
-- -----------------------------------------------------------------------------

REVOKE UPDATE, DELETE, TRUNCATE ON TABLE signals             FROM troy_app;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE excerpts            FROM troy_app;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE narrative_artifacts FROM troy_app;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE corrections         FROM troy_app;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_log           FROM troy_app;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE vendor_scores       FROM troy_app;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE dimension_scores    FROM troy_app;

GRANT SELECT, INSERT ON TABLE signals             TO troy_app;
GRANT SELECT, INSERT ON TABLE excerpts            TO troy_app;
GRANT SELECT, INSERT ON TABLE narrative_artifacts TO troy_app;
GRANT SELECT, INSERT ON TABLE corrections         TO troy_app;
GRANT SELECT, INSERT ON TABLE audit_log           TO troy_app;
GRANT SELECT, INSERT ON TABLE vendor_scores       TO troy_app;
GRANT SELECT, INSERT ON TABLE dimension_scores    TO troy_app;

-- Mutable tables. These are configuration and workflow state, not evidence.
GRANT SELECT, INSERT, UPDATE ON TABLE vendors   TO troy_app;
GRANT SELECT, INSERT, UPDATE ON TABLE contracts TO troy_app;
GRANT SELECT, INSERT, UPDATE ON TABLE alerts    TO troy_app;  -- ack fields only
GRANT SELECT, INSERT, UPDATE ON TABLE orgs      TO troy_app;
GRANT SELECT, INSERT, UPDATE ON TABLE users     TO troy_app;

GRANT USAGE, SELECT ON SEQUENCE signal_chain_seq TO troy_app;

-- -----------------------------------------------------------------------------
-- 2. Trigger enforcement (defence in depth)
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION troy_forbid_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'Table % is append-only. % is not permitted. '
        'Corrections must be inserted as new rows.',
        TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$;

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'signals',
        'excerpts',
        'narrative_artifacts',
        'corrections',
        'audit_log',
        'vendor_scores',
        'dimension_scores'
    ]
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%1$s_append_only ON %1$I', t
        );
        EXECUTE format(
            'CREATE TRIGGER trg_%1$s_append_only
             BEFORE UPDATE OR DELETE ON %1$I
             FOR EACH ROW EXECUTE FUNCTION troy_forbid_mutation()', t
        );
    END LOOP;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. Alerts: allow acknowledgement only
--    Alerts are workflow, not evidence — but the fired facts still shouldn't
--    move. Only the ack/notify columns may change.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION troy_alerts_ack_only()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.vendor_id            IS DISTINCT FROM OLD.vendor_id
    OR NEW.severity             IS DISTINCT FROM OLD.severity
    OR NEW.fired_at             IS DISTINCT FROM OLD.fired_at
    OR NEW.converged_dimensions IS DISTINCT FROM OLD.converged_dimensions
    OR NEW.convergence_score    IS DISTINCT FROM OLD.convergence_score
    OR NEW.threshold_value      IS DISTINCT FROM OLD.threshold_value
    OR NEW.thresholds_version   IS DISTINCT FROM OLD.thresholds_version
    THEN
        RAISE EXCEPTION
            'Only acknowledgement and delivery fields may be updated on alerts.'
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_alerts_ack_only ON alerts;
CREATE TRIGGER trg_alerts_ack_only
    BEFORE UPDATE ON alerts
    FOR EACH ROW EXECUTE FUNCTION troy_alerts_ack_only();

-- -----------------------------------------------------------------------------
-- 4. Derived currency (the Type-2 "is_current" replacement)
--
--    A stored is_current flag would require UPDATEing the superseded row,
--    which append-only forbids. So currency is DERIVED.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE VIEW signal_current AS
SELECT DISTINCT ON (s.vendor_id, s.metric, s.dedup_key)
       s.*
FROM   signals s
LEFT JOIN corrections c ON c.signal_id = s.id
WHERE  c.id IS NULL                    -- exclude superseded signals
  AND  s.validator_verdict = 'accepted'
ORDER BY s.vendor_id, s.metric, s.dedup_key, s.observed_at DESC, s.chain_seq DESC;

COMMENT ON VIEW signal_current IS
    'Latest accepted, non-superseded observation per vendor/metric/dedup_key. '
    'Replaces a stored is_current column, which append-only forbids.';

-- Timeline view for the UI: everything, including superseded rows, flagged.
CREATE OR REPLACE VIEW signal_timeline AS
SELECT s.*,
       (c.id IS NOT NULL)             AS is_superseded,
       c.reason                       AS correction_reason,
       c.actor                        AS corrected_by,
       c.created_at                   AS corrected_at
FROM   signals s
LEFT JOIN corrections c ON c.signal_id = s.id;

GRANT SELECT ON signal_current  TO troy_app;
GRANT SELECT ON signal_timeline TO troy_app;

-- -----------------------------------------------------------------------------
-- 5. Chain integrity guards
-- -----------------------------------------------------------------------------



ALTER TABLE signals
    ADD CONSTRAINT uq_signals_prev_hash UNIQUE (prev_hash);
-- ^ Each hash may be the predecessor of exactly one row. This makes forking
--   the chain impossible rather than merely detectable.
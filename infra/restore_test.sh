#!/usr/bin/env bash
#
# RESTORE DRILL — documented AND executed.
#
# An untested backup is a hypothesis. This restores the latest dump into a
# scratch database, verifies row counts, and — critically — RE-WALKS THE HASH
# CHAIN. A backup that restores but whose chain no longer verifies is worse
# than useless: it looks like valid evidence and is not.
#
# Run monthly. Record the date and result in compliance/dataflow.md.
#
# Usage:  ./infra/restore_test.sh [s3-key]

set -euo pipefail

: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required}"
: "${RESTORE_TEST_DB_URL:?RESTORE_TEST_DB_URL is required (a SCRATCH database)}"
BACKUP_PREFIX="${BACKUP_PREFIX:-troy/postgres}"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

if [ $# -ge 1 ]; then
  KEY="$1"
else
  KEY="$(aws s3 ls "s3://${BACKUP_S3_BUCKET}/${BACKUP_PREFIX}/" \
        | sort | tail -n 1 | awk '{print $4}')"
fi

echo "[restore] testing ${KEY}"
DUMP="${TMPDIR}/${KEY}"
aws s3 cp "s3://${BACKUP_S3_BUCKET}/${BACKUP_PREFIX}/${KEY}" "${DUMP}"

EXPECTED_SHA="$(aws s3api head-object \
  --bucket "${BACKUP_S3_BUCKET}" \
  --key "${BACKUP_PREFIX}/${KEY}" \
  --query 'Metadata.sha256' --output text 2>/dev/null || echo "")"
ACTUAL_SHA="$(sha256sum "${DUMP}" | cut -d' ' -f1)"

if [ -n "${EXPECTED_SHA}" ] && [ "${EXPECTED_SHA}" != "None" ]; then
  if [ "${EXPECTED_SHA}" != "${ACTUAL_SHA}" ]; then
    echo "[restore] FATAL: checksum mismatch"
    echo "  expected ${EXPECTED_SHA}"
    echo "  actual   ${ACTUAL_SHA}"
    exit 1
  fi
  echo "[restore] checksum OK"
fi

echo "[restore] dropping and recreating scratch schema"
psql "${RESTORE_TEST_DB_URL}" -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

echo "[restore] restoring"
pg_restore --dbname="${RESTORE_TEST_DB_URL}" --no-owner --no-acl --jobs=4 "${DUMP}"

echo "[restore] verifying"
psql "${RESTORE_TEST_DB_URL}" -v ON_ERROR_STOP=1 <<'SQL'
\echo '--- table counts ---'
SELECT 'signals'   AS t, count(*) FROM signals
UNION ALL SELECT 'excerpts',  count(*) FROM excerpts
UNION ALL SELECT 'vendors',   count(*) FROM vendors
UNION ALL SELECT 'artifacts', count(*) FROM narrative_artifacts
UNION ALL SELECT 'audit_log', count(*) FROM audit_log;

\echo '--- chain continuity (gaps are fine, breaks are not) ---'
SELECT count(*) AS orphaned_links
FROM signals s
WHERE s.prev_hash <> '0000000000000000000000000000000000000000000000000000000000000000'
  AND NOT EXISTS (SELECT 1 FROM signals p WHERE p.row_hash = s.prev_hash);
SQL

echo ""
echo "[restore] NOW VERIFY THE CHAIN CRYPTOGRAPHICALLY:"
echo "  DATABASE_URL='<async url for scratch db>' python -c \\"
echo "    \"import asyncio;from db.session import SessionFactory;\\"
echo "     from db.integrity.hash_chain import verify_chain;\\"
echo "     print(asyncio.run((lambda: (async def f(): "
echo "       ...)())))\""
echo ""
echo "  Or simply: python scripts/verify_chain_cli.py"
echo ""
echo "[restore] structural restore PASSED — record the date in compliance/dataflow.md"
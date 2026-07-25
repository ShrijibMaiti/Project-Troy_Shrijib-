# PROJECT TROY

A vendor-risk early-warning system for DORA Article 28 ICT third-party oversight.

**Built BY GOD_AXIS.**
**TEAM :- GOD_AXIS**

- **SHRIJIB MAITI** — Domains 5–8: Database & Evidence Integrity, Backend/API & Jobs, Reporting & Register Export, Security & DevOps — plus the Frontend.
- **WRIK SANKAR GHOSH** — https://github.com/Wriksg/Troy-ML  (Domains 1–4: Data Capture & Orchestration, AI/Narrator Layer, Scoring & Risk Engine, Backtest & Calibration)

---

## The Problem

Under DORA (Digital Operational Resilience Act) Article 28, financial institutions are required to continuously oversee the health of their critical ICT vendors — not just at onboarding, but on an ongoing basis. Most compliance teams today rely on static annual questionnaires, security-posture ratings that watch attack surface rather than business health, and GRC platforms that track paperwork rather than reality. None of these catch a vendor's business deterioration — leadership exits, lawsuits, layoffs, sentiment collapse — early enough to act on it, or hand back a result anyone can actually verify.

This half of Project Troy is the part that turns a risk score into something a compliance team can trust, audit, and act on — safely, and without accidentally becoming a liability itself.

---

## What This Repo Does

This repository takes Wrik's validated signal and score output and turns it into a real product:

- **Immutable, tamper-evident evidence store** — every signal row is SHA-256 hash-chained (`row_hash` over content + `prev_hash`), append-only at the database level (INSERT-only triggers, `REVOKE UPDATE/DELETE`), with a full write audit log. Nothing here is "never overwritten" as a promise — it's enforced.
- **FastAPI backend** — versioned `/api/v1`, async throughout, backed by durable job execution (ARQ) so a job doesn't die if a client disconnects mid-run, plus SSE for live status streaming.
- **Evidence pack & register export** — a human-readable PDF evidence pack, and a machine-readable ITS-format export mapped field-by-field against the actual DORA Article 28(3) register templates (RT.01.01–RT.07.01) — LEI, governing law, subcontracting chain, contract dates. This is built to *attach to* a real register, not pretend to be one.
- **Auth & access control** — Clerk-based authentication with full JWT verification (signature, issuer, expiry — not a decoded-but-unverified shortcut), org-scoped row-level access.
- **GDPR-safe by design** — any executive/leadership signal is crypto-shredded: the identifying field is encrypted under a per-subject key, so an erasure request destroys the key without breaking the historical signal chain.
- **React dashboard** — Fleet view, per-vendor detail with citation chips and confidence tiers, an Evidence screen, a Methodology screen, and Compare/Register views.

---

## Why This Matters More Than It Sounds

An AI-generated adverse claim about a named, identifiable company is a real defamation and GDPR exposure if it can't be traced, corrected, or erased properly. This half of Troy exists to make sure every claim that reaches a compliance analyst's desk is provable, correctable, and legally defensible — not just plausible-sounding.

---

## Architecture

```
project-troy-backend/
├── db/                    # Postgres, Type-2 history, hash chain, crypto-shredding
│   ├── models/
│   ├── integrity/         # hash_chain.py, append_only.sql, crypto_shred.py
│   └── ...
├── backend/               # FastAPI, ARQ jobs, SSE, notifiers
│   ├── api/v1/
│   ├── jobs/
│   └── ...
├── reporting/              # PDF evidence pack + ITS machine-readable export
│   └── its_export/
├── security/               # Clerk auth, RBAC, GDPR erasure endpoints
├── frontend/                # React + Vite + Tailwind dashboard
└── shared/schemas/          # Frozen contracts shared with Wrik's pipeline
```

---

## Tech

`FastAPI` · `PostgreSQL` · `SQLAlchemy` · `Redis` · `ARQ`
`React` · `TypeScript` · `Vite` · `Tailwind` · `TanStack Query`
`Clerk` (Auth/RBAC)
`Google Gemma 4` (contract PDF extraction, vendor profiling — optional enrichment, never load-bearing)

---

## Setup

```bash
git clone <repo-url>
cd project-troy-backend
pip install -r requirements.txt
```

**Required environment variables:**
```
DATABASE_URL=postgresql+asyncpg://...
CLERK_SECRET_KEY=...
CLERK_JWKS_URL=https://<your-clerk-domain>/.well-known/jwks.json
```

**Run the API:**
```bash
uvicorn backend.main:app --reload --port 8000
```

**Run the frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## Current Status & Roadmap

**Working today:**
- Full evidence integrity layer — hash chain, append-only enforcement, audit log
- FastAPI backend with durable jobs and SSE
- Clerk authentication with full JWT verification
- ITS-format register export mapped to real DORA templates
- React dashboard, all core screens
- Crypto-shredded GDPR erasure path

**In progress:**
- Live ingestion of Wrik's calibrated scoring output into the database (currently frontend falls back to fixture data where live scores aren't yet populated)
- A couple of frontend endpoint paths still being reconciled against the backend's actual route contracts

**Next up:**
- Full end-to-end handoff from Wrik's backtest-calibrated weights into production scoring
- Alerting (Slack/email/webhook) — sequenced deliberately after scoring is fully validated, not before

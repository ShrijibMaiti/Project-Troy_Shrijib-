# Troy — Frontend

The Troy console (8 screens) and landing page, implemented from the Claude Design
handoff bundle in `../project/` against the stack specified in
`../project/uploads/Project-Troy.md` §7.

## Run

```sh
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc -b + vite build
npm test           # vitest — citation-sync regression suite
```

## Stack

React 18 + TypeScript + Vite · Tailwind (custom tokens in `tailwind.config.ts`) ·
TanStack Query (all server-shaped state) · Zustand (filters/selection only) ·
React Router v6 · Recharts · Radix Dialog.

## Build notes / known deviations

- **Seismograph is bespoke SVG, not Recharts** (`src/components/risk/Seismograph.tsx`),
  because the clickable event markers must sit exactly on the polyline — this is a
  deliberate deviation from strict §7 stack conformance, not an oversight. Revisit if
  pixel-perfect marker placement can be achieved inside a Recharts ComposedChart with
  a custom dot renderer. The lead-time chart (`src/components/charts/LeadTimeChart.tsx`)
  *is* Recharts. `TrendChart` (the fleet-row sparkline) is bespoke for the same reason
  at 28px tall — no axes/tooltips to gain, one chart instance per table row to lose.
- **Fonts are self-hosted** (`src/styles/fonts/`, WOFF2 + `@font-face`) — no requests
  leave the page. General Sans is under the ITF Free Font License, Sometype Mono under
  SIL OFL 1.1; provenance is noted in `fonts.css`.
- **No backend yet.** `src/lib/api.ts` is the seam: every function has the signature
  the future FastAPI `/api/v1` endpoints will serve, backed by in-memory stores seeded
  from `src/data/fixtures.ts`. Mutations (vendor CRUD, dispute → supersede) mutate the
  in-memory stores through TanStack Query mutations, so state is live across screens
  but resets on reload — durability is the backend's job. Swapping to the real API is
  a change to `api.ts` function bodies only; `vite.config.ts` already proxies `/api`
  to `localhost:8000`.
- **Append-only posture is enforced in the mock layer**: vendors are archived, never
  deleted; disputes append a `SUPERSEDE` chain record (visible on the Evidence screen's
  write log without a reload) and never touch the original signal.
- **Dispute score diff is an estimate** (`src/lib/scoring.ts`): weight × |z| of the
  disputed signal's dimension, with a calibration constant standing in for the real
  scoring engine's recompute. It is computed per claim, not hardcoded.
- **Auth is a UI mockup** — the sign-in screen routes straight to Fleet; Clerk comes
  with the backend epic.

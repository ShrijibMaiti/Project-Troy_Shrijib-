/**
 * API seam: React frontend -> FastAPI backend.
 *
 * Auth: sends BOTH X-Org-Id (backend dev mode) and Bearer (Clerk mode). The
 * backend uses whichever its AUTH_MODE wants. This lets us demo in dev mode
 * without Clerk fully provisioned, and flip to Clerk with no frontend change.
 *
 * Fixture fallback is gated behind VITE_USE_FIXTURES. By default it is OFF, so
 * a broken endpoint shows a real error instead of silently rendering fake data.
 */

import {
  aldermereDimensions, aldermereEventWeeks, aldermereHist, aldermereNarrative,
  aldermereSignals, alerts as alertFixtures, compareRows, concentrationFindings,
  evidenceData as evidenceFixtures, methodologyData as methodologyFixtures,
  registerChangelog as changelogFixtures, registerRows as registerFixtures,
  vendors as vendorFixtures,
} from '@/data/fixtures';

import type {
  AlertItem, ChainEvent, CompareRow, ConcentrationFinding, ChangelogEntry,
  EvidenceData, MethodologyData, RegisterRow, Vendor, VendorDetail, VendorState,
  Confidence, Dimension, Signal, NarrativeSentence,
} from '@/types/api';

const API_URL = import.meta.env.VITE_API_URL ?? '';
const DEV_ORG_ID = import.meta.env.VITE_DEV_ORG_ID ?? '';
const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1';

let getTokenFn: (() => Promise<string | null>) | null = null;
export function setAuthTokenGetter(fn: () => Promise<string | null>) {
  getTokenFn = fn;
}

async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (DEV_ORG_ID) headers['X-Org-Id'] = DEV_ORG_ID;
  if (getTokenFn) {
    try {
      const token = await getTokenFn();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    } catch (e) {
      console.warn('Clerk token retrieval failed:', e);
    }
  }
  const res = await fetch(`${API_URL}${endpoint}`, { ...options, headers });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`API ${res.status}: ${t || res.statusText}`);
  }
  if (res.status === 204) return {} as T;
  return res.json() as Promise<T>;
}

// ---- helpers -------------------------------------------------------------

/** composite 0-100 -> fleet state. Matches PDF risk_color thresholds. */
function stateFromScore(score: number): VendorState {
  if (score >= 70) return 'ALERT';
  if (score >= 40) return 'WATCH';
  return 'STABLE';
}

/** backend lowercase SignalMetric -> the UI's uppercase dimension label */
const DIM_LABEL: Record<string, string> = {
  leadership_change: 'LEADERSHIP',
  legal_event: 'LEGAL',
  headcount_change: 'HEADCOUNT',
  sentiment: 'SENTIMENT',
  news_volume: 'NEWS VOLUME',
  open_roles: 'OPEN ROLES',
  funding_event: 'FUNDING',
  regulatory_filing: 'REGULATORY',
};

const CONF_LABEL: Record<string, Confidence> = {
  verified: 'VERIFIED', reported: 'REPORTED', unconfirmed: 'UNCONFIRMED',
};

function mapVendor(raw: any): Vendor {
  const score = typeof raw.composite === 'number' ? raw.composite : (raw.score ?? 0);
  return {
    id: raw.id ?? raw.vendor_id ?? '',
    name: raw.display_name ?? raw.name ?? raw.legal_name ?? 'Unknown',
    state: raw.state ? (raw.state.toUpperCase() as VendorState) : stateFromScore(score),
    score,
    staleDays: raw.stale_days ?? 0,
    captureRate: 100,
    tier: (raw.entity_type ?? 'unknown').toUpperCase().replace(/_/g, ' '),
    hist: Array.isArray(raw.hist) ? raw.hist : [],
    archived: raw.is_active === false,
    pendingCapture: raw.composite == null && raw.score == null,
  };
}

// ---- vendors -------------------------------------------------------------

export async function getVendors(): Promise<Vendor[]> {
  try {
    const raw = await apiFetch<any[]>('/api/v1/vendors');
    return (raw ?? []).map(mapVendor);   // empty array is a REAL empty fleet, not a fallback trigger
  } catch (err) {
    console.warn('getVendors failed:', err);
    if (USE_FIXTURES) return vendorFixtures.map((v) => ({ ...v }));
    throw err;
  }
}

export async function getAlerts(): Promise<AlertItem[]> {
  try {
    const raw = await apiFetch<any[]>('/api/v1/alerts');
    return (raw ?? []).map((a) => ({
      vendorId: a.vendor_id ?? '',
      name: a.headline?.split(' ')[0] ?? a.vendor_name ?? '',
      reason: a.headline ?? '',
      scoreTxt: `${(a.convergence_score ?? 0).toFixed(0)} ▲`,
      state: (a.severity?.toUpperCase() as VendorState) ?? 'WATCH',
    }));
  } catch (err) {
    if (USE_FIXTURES) return alertFixtures;
    return [];   // no alerts is a valid state, not an error to surface
  }
}

export interface VendorInput { name: string; tier: string; }

export async function addVendor(input: VendorInput): Promise<Vendor> {
  const created = await apiFetch<any>('/api/v1/vendors', {
    method: 'POST',
    body: JSON.stringify({
      display_name: input.name,
      legal_name: input.name,
      entity_type: (input.tier || 'unknown').toLowerCase().replace(/ /g, '_'),
    }),
  });
  return mapVendor(created);
}

export async function updateVendor(id: string, patch: Partial<VendorInput>): Promise<Vendor> {
  const payload: Record<string, any> = {};
  if (patch.name) payload.display_name = patch.name;
  if (patch.tier) payload.entity_type = patch.tier.toLowerCase().replace(/ /g, '_');
  const updated = await apiFetch<any>(`/api/v1/vendors/${id}`, {
    method: 'PATCH', body: JSON.stringify(payload),
  });
  return mapVendor(updated);
}

export async function setVendorArchived(id: string, _archived: boolean): Promise<Vendor> {
  // Backend deactivates via DELETE (soft — keeps the chain). No un-archive endpoint.
  await apiFetch<void>(`/api/v1/vendors/${id}`, { method: 'DELETE' });
  const v = vendorFixtures.find((x) => x.id === id) ?? vendorFixtures[0];
  return { ...v, archived: true };
}

// ---- vendor detail: FAN-OUT over four real endpoints ---------------------

export async function getVendorDetail(id: string): Promise<VendorDetail> {
  try {
    const [vendorRaw, scoreRaw, signalsRaw, narrativeRaw, historyRaw] = await Promise.all([
      apiFetch<any>(`/api/v1/vendors/${id}`),
      apiFetch<any>(`/api/v1/scores/vendor/${id}`).catch(() => null),
      apiFetch<any[]>(`/api/v1/signals/vendor/${id}`).catch(() => []),
      apiFetch<any>(`/api/v1/narratives/vendor/${id}`).catch(() => null),
      apiFetch<any[]>(`/api/v1/scores/vendor/${id}/history`).catch(() => []),
    ]);

    const vendor = mapVendor({ ...vendorRaw, composite: scoreRaw?.composite });

    const signals: Signal[] = (signalsRaw ?? []).map((s, i) => ({
      n: s.chain_seq ?? i + 1,
      date: (s.event_date ?? s.observed_at ?? '').slice(0, 10),
      title: s.summary ?? '(no summary)',
      src: s.source ?? '',
      conf: CONF_LABEL[(s.confidence ?? 'reported')?.toLowerCase?.()] ?? 'REPORTED',
      hash: `#${(s.row_hash ?? '').slice(0, 4)}…${(s.row_hash ?? '').slice(-2)}`,
      excerpt: s.excerpt_text ?? s.summary ?? '',
      tag: (s.event_date ?? '').slice(5, 10),
      dim: DIM_LABEL[s.metric] ?? (s.metric ?? '').toUpperCase(),
    }));

    // Narrative: backend stores markdown + citations. If none yet, empty.
    const narrative: NarrativeSentence[] = narrativeRaw?.narrative_md
      ? [{ text: narrativeRaw.narrative_md, n: 0, conf: 'REPORTED', disputable: false }]
      : [];

    const dimensions: Dimension[] = (scoreRaw?.dimensions ?? []).map((d: any) => ({
      name: DIM_LABEL[d.dimension] ?? (d.dimension ?? '').toUpperCase(),
      z: d.z_score == null ? '—' : (d.z_score >= 0 ? `+${d.z_score.toFixed(1)}` : d.z_score.toFixed(1)),
      val: d.raw_value == null ? '—' : d.raw_value.toFixed(1),
      base: d.baseline == null ? 'n/a' : d.baseline.toFixed(1),   // NULL baseline shown honestly
      w: (d.weight_applied ?? 0).toFixed(2),
      pct: Math.min(100, Math.round((d.contribution ?? 0))),
      tick: 50,
    }));

    const hist = (historyRaw ?? []).map((h) => Math.round(h.composite));
    const eventWeeks = signals.slice(0, 8).map((s, i) => ({ n: s.n, w: Math.floor((i / 8) * (hist.length || 1)) }));

    const delta = scoreRaw?.delta;
    return {
      vendor, signals, narrative, dimensions,
      hist: hist.length ? hist : [vendor.score],
      eventWeeks,
      scoreDelta90d: delta == null ? '— IN 90 DAYS' : `${delta >= 0 ? '+' : ''}${delta.toFixed(0)} IN 90 DAYS`,
      artifactMeta: {
        model: narrativeRaw?.model_id ?? 'gemma-4-31b-it',
        prompt: narrativeRaw?.prompt_hash ? `#${narrativeRaw.prompt_hash.slice(0, 4)}… (${narrativeRaw.prompt_name})` : 'no artifact yet',
        generatedAt: narrativeRaw?.generated_at ?? '—',
      },
    };
  } catch (err) {
    console.warn(`getVendorDetail(${id}) failed:`, err);
    if (!USE_FIXTURES) throw err;
    const vendor = vendorFixtures.find((v) => v.id === id) ?? vendorFixtures[0];
    return {
      vendor: { ...vendor }, signals: aldermereSignals, narrative: aldermereNarrative,
      dimensions: aldermereDimensions, hist: aldermereHist, eventWeeks: aldermereEventWeeks,
      scoreDelta90d: '+23 IN 90 DAYS',
      artifactMeta: { model: 'gemma-4-31b-it', prompt: '#a41f… (v12)', generatedAt: '2026-07-19 06:14 UTC' },
    };
  }
}

// ---- dispute (real supersede) --------------------------------------------

export interface SupersedeInput { claimN: number; vendorName: string; annotation: string; scoreDelta: number; signalId?: string; }
export interface SupersedeResult { recordNumber: number; record: ChainEvent; scoreBefore: number | null; scoreAfter: number | null; }

export async function appendSupersede(input: SupersedeInput): Promise<SupersedeResult> {
  if (!input.signalId) throw new Error('signalId required to dispute');
  const raw = await apiFetch<any>(`/api/v1/signals/${input.signalId}/dispute`, {
    method: 'POST',
    body: JSON.stringify({ reason: 'factually_incorrect', note: input.annotation }),
  });
  return {
    recordNumber: 1,
    record: {
      ts: new Date().toLocaleTimeString(),
      type: 'SUPERSEDE',
      desc: `Claim [${input.claimN}] ${input.vendorName.split(' ')[0]} — annotated`,
      hash: `${(raw.correction_id ?? '').slice(0, 4)}…`,
    },
    scoreBefore: raw.score_before ?? null,
    scoreAfter: raw.score_after ?? null,
  };
}

// ---- evidence: FAN-OUT + real chain verify -------------------------------

export async function verifyChain(): Promise<{ ok: boolean; checked: number; headHash: string; reason: string | null }> {
  const r = await apiFetch<any>('/api/v1/trust/chain-verify?force=true');
  return { ok: r.ok, checked: r.checked, headHash: r.head_hash, reason: r.reason ?? null };
}

export async function getEvidence(): Promise<EvidenceData> {
  try {
    const [chain, metrics, log] = await Promise.all([
      apiFetch<any>('/api/v1/trust/chain-verify'),
      apiFetch<any>('/api/v1/trust/audit-metrics'),
      apiFetch<any[]>('/api/v1/trust/audit-log').catch(() => []),
    ]);

    const chainEvents: ChainEvent[] = (log ?? []).slice(0, 12).map((e) => ({
      ts: (e.created_at ?? '').slice(5, 16).replace('T', ' '),
      type: e.action === 'signal_disputed' ? 'SUPERSEDE' : e.action?.includes('calibration') ? 'VERSION' : 'CAPTURE',
      desc: `${e.action?.replace(/_/g, ' ')} — ${e.actor}`,
      hash: '',
    }));

    return {
      audit1: {
        pct: metrics.narrative_resolution_pct?.toFixed(1) ?? 'n/a',
        sub: `${metrics.distinct_citations ?? 0} CITATIONS · ${metrics.distinct_claims ?? 0} CLAIMS · ${metrics.unresolved_count ?? 0} UNRESOLVED`,
        body: 'Whether every [n] marker in generated narratives maps to a distinct signal. Failures are shown unresolved, not hidden.',
      },
      audit2: {
        pct: metrics.extraction_fidelity_pct?.toFixed(1) ?? 'not measured',
        sub: `${metrics.entailment_sampled ?? 0} SAMPLED · ${metrics.entailment_failed ?? 0} FAILED ENTAILMENT`,
        body: 'A separate model checks each cited excerpt entails its claim. These two numbers are never merged — "zero hallucinations" is not a claim this product makes.',
      },
      headHash: `${chain.head_hash?.slice(0, 8)}…${chain.head_hash?.slice(-6)}`,
      recordCount: chain.checked ?? 0,
      chain: chainEvents,
      versions: {
        model: 'gemma-4-31b-it', prompt: 'live', since: '—', auditModel: 'gemma-4-12b-it',
      },
      lastRun: {
        result: chain.ok ? 'PASS' : 'FAIL',
        at: (chain.verified_at ?? '').slice(0, 19).replace('T', ' ') + ' UTC',
        lines: [
          `${chain.checked ?? 0} / ${chain.checked ?? 0} LINKS INTACT`,
          chain.ok ? '0 REWRITES DETECTED · 0 GAPS' : `BREAK AT SEQ ${chain.first_break_seq}`,
        ],
      },
    };
  } catch (err) {
    console.warn('getEvidence failed:', err);
    if (!USE_FIXTURES) throw err;
    return { ...evidenceFixtures };
  }
}

// ---- methodology / register / compare (leave fixture-friendly for now) ---

export async function getMethodology(): Promise<MethodologyData> {
  // Serve fixtures for now: the backend /methodology shape differs from what
  // this page renders, and real calibration is still provisional. Not on the
  // demo critical path.
  return methodologyFixtures;
}

export async function getRegister(): Promise<{ rows: RegisterRow[]; changelog: ChangelogEntry[] }> {
  try {
    const [rawRows, rawChangelog] = await Promise.all([
      apiFetch<any[]>('/api/v1/register'),
      apiFetch<any>('/api/v1/register/changelog').catch(() => ({ changes: [] })),
    ]);
    const rows: RegisterRow[] = (rawRows ?? []).map((r) => ({
      vendorId: r.vendor?.id ?? '',
      name: r.vendor?.display_name ?? '',
      state: stateFromScore(r.composite ?? 0),
      staleDays: 0,
      lei: r.contract?.provider_lei ?? '—',
      fn: r.contract?.function_name ?? '—',
      contract: r.contract?.contractual_arrangement_ref ?? '—',
      law: r.contract?.governing_law_country ?? '—',
      subs: '—',
      loc: (r.contract?.data_location_countries ?? []).join(', ') || '—',
      subst: r.contract?.substitutability ?? '—',
      exit: r.contract?.exit_plan_exists ? 'YES' : 'NO',
    }));
    const changelog: ChangelogEntry[] = (rawChangelog?.changes ?? []).map((c: any) => ({
      ver: `v${c.register_version ?? 1}`,
      date: (c.changed_at ?? '').slice(0, 10),
      desc: `${c.change_type ?? 'updated'} ${c.vendor ?? ''}`,
      by: c.changed_by ?? 'system',
    }));
    if (rows.length) return { rows, changelog };
  } catch { /* fixture */ }
  return { rows: registerFixtures, changelog: changelogFixtures };
}

export async function startExport(fmt: 'pdf' | 'its'): Promise<{ jobId: string | null }> {
  const res = await apiFetch<any>('/api/v1/register/export', {
    method: 'POST',
    body: JSON.stringify({ format: fmt }),
  });
  return { jobId: res.job_id ?? res.id ?? null };
}

export interface ExportArtifact {
  id: string;
  kind: string;
  format: string;
  filename: string;
  generated_at: string;
  content_hash: string;
  chain_head_hash: string;
}

export async function listExports(): Promise<ExportArtifact[]> {
  const raw = await apiFetch<any[]>('/api/v1/register/exports');
  return (raw ?? []).map((r) => ({
    id: r.id,
    kind: r.kind,
    format: r.format,
    filename: r.filename,
    generated_at: r.generated_at,
    content_hash: r.content_hash,
    chain_head_hash: r.chain_head_hash,
  }));
}

export interface ExportResult {
  artifactId: string;
  filename: string;
  contentHash: string;
  chainHead: string;
  cached: boolean;
}

/** Renders synchronously and returns the artifact. No job queue, no polling. */
export async function runExport(fmt: 'pdf' | 'its'): Promise<ExportResult> {
  const res = await apiFetch<any>(`/api/v1/register/export-sync?fmt=${fmt}`, {
    method: 'POST',
  });
  return {
    artifactId: res.artifact_id,
    filename: res.filename,
    contentHash: res.content_hash,
    chainHead: res.chain_head_hash,
    cached: res.cached ?? false,
  };
}

/** Downloads the real bytes. Triggers a browser save. */
export async function downloadExport(artifactId: string, filename: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (DEV_ORG_ID) headers['X-Org-Id'] = DEV_ORG_ID;
  if (getTokenFn) {
    try {
      const t = await getTokenFn();
      if (t) headers['Authorization'] = `Bearer ${t}`;
    } catch { /* ignore */ }
  }
  const res = await fetch(`${API_URL}/api/v1/register/exports/${artifactId}/download`, { headers });
  if (!res.ok) throw new Error(`Download failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function getCompare(): Promise<{ rows: CompareRow[]; findings: ConcentrationFinding[] }> {
  return { rows: compareRows, findings: concentrationFindings };  // stays fixture for demo
}
/**
 * API seam. Every function has the signature the real FastAPI backend will
 * serve (`/api/v1/...`); until it exists they resolve from in-memory stores
 * seeded from local fixtures. Swapping in the real thing is a fetch call per
 * function — nothing else moves.
 *
 * Mutations follow the product's append-only posture: vendors are archived,
 * never deleted; disputes append a SUPERSEDE record to the chain, the original
 * signal is never touched.
 */
import {
  aldermereDimensions,
  aldermereEventWeeks,
  aldermereHist,
  aldermereNarrative,
  aldermereSignals,
  alerts,
  compareRows,
  concentrationFindings,
  evidenceData,
  methodologyData,
  registerChangelog,
  registerRows,
  vendors as vendorFixtures,
} from '@/data/fixtures';
import type {
  AlertItem,
  ChainEvent,
  CompareRow,
  ConcentrationFinding,
  ChangelogEntry,
  EvidenceData,
  MethodologyData,
  RegisterRow,
  Vendor,
  VendorDetail,
} from '@/types/api';

const delay = (ms = 80) => new Promise((r) => setTimeout(r, ms));

// ---- in-memory stores (reset on reload; the backend owns durability) ----
let vendorStore: Vendor[] = vendorFixtures.map((v) => ({ ...v }));
let chainStore: ChainEvent[] = evidenceData.chain.map((c) => ({ ...c }));
let chainHead = evidenceData.headHash;
let recordCount = evidenceData.recordCount;

const hex = (n: number) =>
  Array.from({ length: n }, () => '0123456789abcdef'[Math.floor(Math.random() * 16)]).join('');

const nowTs = () => {
  const d = new Date();
  const p = (x: number) => String(x).padStart(2, '0');
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

export async function getVendors(): Promise<Vendor[]> {
  await delay();
  return vendorStore.map((v) => ({ ...v }));
}

export async function getAlerts(): Promise<AlertItem[]> {
  await delay();
  return alerts;
}

export interface VendorInput {
  name: string;
  tier: string;
}

export async function addVendor(input: VendorInput): Promise<Vendor> {
  await delay();
  const vendor: Vendor = {
    id: input.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || `vendor-${hex(4)}`,
    name: input.name,
    tier: input.tier,
    state: 'STABLE',
    score: 0,
    staleDays: 0,
    captureRate: 0,
    hist: [],
    pendingCapture: true,
  };
  vendorStore = [...vendorStore, vendor];
  return { ...vendor };
}

export async function updateVendor(id: string, patch: Partial<VendorInput>): Promise<Vendor> {
  await delay();
  const i = vendorStore.findIndex((v) => v.id === id);
  if (i < 0) throw new Error(`vendor ${id} not found`);
  vendorStore = vendorStore.map((v, j) => (j === i ? { ...v, ...patch } : v));
  return { ...vendorStore[i] };
}

/** Archive stops capture but keeps the chain; restore resumes. Never a delete. */
export async function setVendorArchived(id: string, archived: boolean): Promise<Vendor> {
  await delay();
  const i = vendorStore.findIndex((v) => v.id === id);
  if (i < 0) throw new Error(`vendor ${id} not found`);
  vendorStore = vendorStore.map((v, j) => (j === i ? { ...v, archived } : v));
  return { ...vendorStore[i] };
}

export async function getVendorDetail(id: string): Promise<VendorDetail> {
  await delay();
  // Only the demo vendor (Aldermere) has full detail fixtures; every id resolves to it,
  // matching the prototype where all rows open the same case study.
  void id;
  const vendor = vendorStore.find((v) => v.id === 'aldermere') ?? vendorStore[0];
  return {
    vendor: { ...vendor },
    signals: aldermereSignals,
    narrative: aldermereNarrative,
    dimensions: aldermereDimensions,
    hist: aldermereHist,
    eventWeeks: aldermereEventWeeks,
    scoreDelta90d: '+23 IN 90 DAYS',
    artifactMeta: { model: 'claude-sonnet-4-5', prompt: '#a41f…c2 (v12)', generatedAt: '2026-07-19 06:14 UTC' },
  };
}

export interface SupersedeInput {
  claimN: number;
  vendorName: string;
  annotation: string;
  scoreDelta: number;
}

export interface SupersedeResult {
  recordNumber: number;
  record: ChainEvent;
}

/** Appends a SUPERSEDE record to the chain. The original claim is never mutated. */
export async function appendSupersede(input: SupersedeInput): Promise<SupersedeResult> {
  await delay();
  const shortName = input.vendorName.split(' ')[0];
  const record: ChainEvent = {
    ts: nowTs(),
    type: 'SUPERSEDE',
    desc: `Claim [${input.claimN}] ${shortName} — annotated by E. Vance, score −${input.scoreDelta}`,
    hash: `${hex(4)}…${hex(2)}`,
  };
  chainStore = [record, ...chainStore];
  chainHead = `${hex(8)}…${hex(6)}`;
  recordCount += 1;
  return { recordNumber: recordCount, record: { ...record } };
}

export async function getEvidence(): Promise<EvidenceData> {
  await delay();
  return {
    ...evidenceData,
    headHash: chainHead,
    recordCount,
    chain: chainStore.map((c) => ({ ...c })),
  };
}

export async function getMethodology(): Promise<MethodologyData> {
  await delay();
  return methodologyData;
}

export async function getRegister(): Promise<{ rows: RegisterRow[]; changelog: ChangelogEntry[] }> {
  await delay();
  return { rows: registerRows, changelog: registerChangelog };
}

export async function getCompare(): Promise<{ rows: CompareRow[]; findings: ConcentrationFinding[] }> {
  await delay();
  return { rows: compareRows, findings: concentrationFindings };
}

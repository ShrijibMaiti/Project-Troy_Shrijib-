export type VendorState = 'ALERT' | 'WATCH' | 'STABLE';
export type Confidence = 'VERIFIED' | 'REPORTED' | 'UNCONFIRMED';

export interface Vendor {
  id: string;
  name: string;
  state: VendorState;
  score: number;
  staleDays: number;
  captureRate: number;
  tier: string;
  hist: number[];
  /** archived vendors stop capture but keep their chain — never hard-deleted */
  archived?: boolean;
  /** true until the first capture run has produced signals */
  pendingCapture?: boolean;
}

export interface AlertItem {
  vendorId: string;
  name: string;
  reason: string;
  scoreTxt: string;
  state: VendorState;
}

export interface Signal {
  id?: string;       // real backend UUID; absent in fixtures
  n: number;
  date: string;
  title: string;
  src: string;
  conf: Confidence;
  hash: string;
  excerpt: string;
  tag: string;
  /** the scoring dimension this signal feeds (matches Dimension.name) */
  dim: string;
}

export interface NarrativeSentence {
  text: string;
  n: number;
  conf: Confidence;
  disputable: boolean;
}

export interface Dimension {
  name: string;
  z: string;
  val: string;
  base: string;
  w: string;
  pct: number;
  tick: number;
}

export interface VendorDetail {
  vendor: Vendor;
  signals: Signal[];
  narrative: NarrativeSentence[];
  dimensions: Dimension[];
  /** weekly composite scores, Jan–Jul */
  hist: number[];
  /** signal n → week index into hist */
  eventWeeks: { n: number; w: number }[];
  scoreDelta90d: string;
  artifactMeta: ArtifactMeta;
}

export interface ArtifactMeta {
  model: string;
  prompt: string;
  generatedAt: string;
}

export type ChainEventType = 'CAPTURE' | 'SUPERSEDE' | 'VERSION';

export interface ChainEvent {
  ts: string;
  type: ChainEventType;
  desc: string;
  hash: string;
}

export interface EvidenceData {
  audit1: { pct: string; sub: string; body: string };
  audit2: { pct: string; sub: string; body: string };
  headHash: string;
  recordCount: number;
  chain: ChainEvent[];
  versions: { model: string; prompt: string; since: string; auditModel: string };
  lastRun: { result: string; at: string; lines: string[] };
}

export interface LeadBucket {
  label: string;
  n: number;
}

export interface MethodologyData {
  leadBuckets: LeadBucket[];
  medianDays: number;
  stats: { value: string; label: string }[];
  weights: { name: string; v: number }[];
  weightsNote: string;
  thresholdBody: string;
  thresholdTable: string[];
  thresholdNote: string;
  limitations: { num: string; text: string }[];
}

export interface RegisterRow {
  vendorId: string;
  name: string;
  state: VendorState;
  staleDays: number;
  lei: string;
  fn: string;
  contract: string;
  law: string;
  subs: string;
  loc: string;
  subst: string;
  exit: string;
}

export interface ChangelogEntry {
  ver: string;
  date: string;
  desc: string;
  by: string;
}

/** level: 0 = none, 1 = shared, 2 = concentrated */
export interface CompareCell {
  value: string;
  level: 0 | 1 | 2;
}

export interface CompareRow {
  vendorId: string;
  name: string;
  score: number;
  cloud: CompareCell;
  region: CompareCell;
  kyc: CompareCell;
  sector: CompareCell;
}

export interface ConcentrationFinding {
  stat: string;
  tone: 'amber' | 'red';
  label: string;
  body: string;
}

export interface NotificationChannel {
  id: string;
  name: string;
  target: string;
}

export interface SeriesPoint {
  date: string;
  failed: number | null;
  control: number | null;
}

export interface MethodologyLive {
  calibrated: boolean;
  engineVersion: string;
  status: string;
  summary: string;
  eventsTested: number;
  controls: number;
  leadDays: number | null;
  controlFpRate: string | null;
  peakFailed: number | null;
  peakControl: number | null;
  failedName: string;
  controlName: string;
  failureDate: string | null;
  series: SeriesPoint[];
  weights: { name: string; v: number }[];
  thresholds: { label: string; value: string }[];
  limitations: string[];
}
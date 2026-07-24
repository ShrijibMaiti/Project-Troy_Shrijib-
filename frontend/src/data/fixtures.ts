import type {
  AlertItem,
  ChangelogEntry,
  CompareRow,
  ConcentrationFinding,
  Dimension,
  EvidenceData,
  MethodologyData,
  NarrativeSentence,
  NotificationChannel,
  RegisterRow,
  Signal,
  Vendor,
} from '@/types/api';

export const vendors: Vendor[] = [
  { id: 'aldermere', name: 'Aldermere Analytics Ltd', state: 'ALERT', score: 71, staleDays: 5, captureRate: 94, tier: 'PRIVATE·T2', hist: [24, 26, 25, 28, 31, 30, 34, 38, 37, 42, 48, 47, 53, 58, 62, 61, 66, 71] },
  { id: 'quarterpoint', name: 'Quarterpoint Data GmbH', state: 'WATCH', score: 52, staleDays: 1, captureRate: 99, tier: 'PRIVATE·T2', hist: [30, 31, 33, 32, 35, 34, 36, 39, 41, 40, 44, 43, 46, 45, 48, 50, 51, 52] },
  { id: 'provene', name: 'Provene KYC', state: 'WATCH', score: 48, staleDays: 2, captureRate: 97, tier: 'PRIVATE·T1', hist: [38, 40, 39, 42, 41, 44, 43, 45, 44, 46, 45, 47, 46, 48, 47, 49, 48, 48] },
  { id: 'straitlace', name: 'Straitlace Payroll', state: 'WATCH', score: 44, staleDays: 1, captureRate: 100, tier: 'PUBLIC·T1', hist: [28, 29, 31, 30, 33, 35, 34, 37, 36, 39, 38, 41, 40, 42, 43, 42, 44, 44] },
  { id: 'ferrous', name: 'Ferrous Freight Systems', state: 'STABLE', score: 26, staleDays: 11, captureRate: 71, tier: 'PRIVATE·T3', hist: [24, 25, 24, 26, 25, 27, 26, 25, 27, 26, 28, 27, 26, 27, 26, 27, 26, 26] },
  { id: 'ozanam', name: 'Ozanam Hosting BV', state: 'STABLE', score: 22, staleDays: 1, captureRate: 100, tier: 'PUBLIC·T1', hist: [20, 21, 20, 22, 21, 23, 22, 21, 22, 23, 22, 21, 22, 23, 22, 21, 22, 22] },
  { id: 'kestrel', name: 'Kestrel Cloud Services', state: 'STABLE', score: 18, staleDays: 0, captureRate: 100, tier: 'PUBLIC·T1', hist: [17, 18, 17, 19, 18, 17, 18, 19, 18, 17, 18, 17, 18, 19, 18, 17, 18, 18] },
  { id: 'miravel', name: 'Miravel CX', state: 'STABLE', score: 15, staleDays: 3, captureRate: 98, tier: 'PRIVATE·T1', hist: [14, 15, 14, 16, 15, 14, 15, 16, 15, 14, 15, 14, 15, 16, 15, 14, 15, 15] },
];

export const alerts: AlertItem[] = [
  { vendorId: 'aldermere', name: 'Aldermere Analytics Ltd', reason: 'Crossed alert threshold 17 Jul — leadership, legal, headcount converging', scoreTxt: '71 ▲', state: 'ALERT' },
  { vendorId: 'quarterpoint', name: 'Quarterpoint Data GmbH', reason: 'Approaching threshold — sentiment + news volume rising 6 consecutive weeks', scoreTxt: '52 ▲', state: 'WATCH' },
];

export const aldermereSignals: Signal[] = [
  { n: 1, date: '2026-03-12', title: 'Annual accounts filed 41 days late', src: 'Companies House', conf: 'VERIFIED', hash: '#c41a…9e', excerpt: 'Accounts for period ending 31 Dec 2025 received 11 Mar 2026; statutory deadline 30 Jan 2026.', tag: 'MAR 12', dim: 'LEGAL' },
  { n: 2, date: '2026-04-02', title: 'CFO departure announced', src: 'Company press release', conf: 'VERIFIED', hash: '#d02b…41', excerpt: 'Aldermere Analytics announces that Chief Financial Officer R. Halloway will step down effective 30 April.', tag: 'APR 02', dim: 'LEADERSHIP' },
  { n: 3, date: '2026-04-20', title: 'Engineering postings down 63% q/q', src: 'Aggregated job boards', conf: 'VERIFIED', hash: '#e13c…77', excerpt: 'Open engineering roles fell from 24 (Q4 avg) to 9; core platform roles removed without refill.', tag: 'APR 20', dim: 'OPEN ROLES' },
  { n: 4, date: '2026-05-06', title: 'Employee sentiment slides 3.9 → 3.1', src: 'Glassdoor aggregate', conf: 'REPORTED', hash: '#f24d…08', excerpt: '"Third reorg in a year. Leadership has stopped communicating roadmap." — 60-day rolling average.', tag: 'MAY 06', dim: 'SENTIMENT' },
  { n: 5, date: '2026-05-28', title: 'Loss of Meridian Bank contract reported', src: 'FinTech Register (trade press)', conf: 'REPORTED', hash: '#a35e…b2', excerpt: 'Two sources say Meridian will not renew its data-enrichment contract with Aldermere at June expiry.', tag: 'MAY 28', dim: 'NEWS VOLUME' },
  { n: 6, date: '2026-06-15', title: 'Workforce reduction of ~18%', src: 'UK Tech Register', conf: 'REPORTED', hash: '#b46f…3d', excerpt: 'Aldermere cut approximately 40 of 220 staff on 12 June, concentrated in delivery and support.', tag: 'JUN 15', dim: 'HEADCOUNT' },
  { n: 7, date: '2026-07-02', title: 'County court judgment vs subsidiary', src: 'Registry Trust', conf: 'VERIFIED', hash: '#c57a…66', excerpt: 'CCJ for £84,200 entered against Aldermere Data Services Ltd, unpaid supplier invoice, 28 Jun.', tag: 'JUL 02', dim: 'LEGAL' },
  { n: 8, date: '2026-07-19', title: 'Open roles at 2 vs baseline 24', src: 'Aggregated job boards', conf: 'VERIFIED', hash: '#d68b…19', excerpt: 'Hiring effectively frozen; the two remaining postings are both in collections/AR.', tag: 'JUL 19', dim: 'OPEN ROLES' },
];

export const aldermereNarrative: NarrativeSentence[] = [
  { text: 'Aldermere Analytics entered the alert band on 17 July after six months of correlated deterioration across leadership, headcount and legal dimensions.', n: 8, conf: 'VERIFIED', disputable: false },
  { text: 'The company filed its annual accounts 41 days past the statutory deadline in March', n: 1, conf: 'VERIFIED', disputable: false },
  { text: 'and announced the departure of its CFO two weeks later, the second executive exit in twelve months.', n: 2, conf: 'VERIFIED', disputable: false },
  { text: 'Engineering job postings contracted 63% quarter-on-quarter through April', n: 3, conf: 'VERIFIED', disputable: false },
  { text: 'while aggregate employee sentiment fell from 3.9 to 3.1 over sixty days.', n: 4, conf: 'REPORTED', disputable: true },
  { text: 'Trade press reports — not yet confirmed by either party — indicate the loss of the Meridian Bank enrichment contract at June renewal.', n: 5, conf: 'REPORTED', disputable: true },
  { text: 'A workforce reduction of approximately 18% followed on 12 June, concentrated in delivery and support functions', n: 6, conf: 'REPORTED', disputable: true },
  { text: 'and a county court judgment for an unpaid supplier invoice was entered against its data-services subsidiary on 28 June.', n: 7, conf: 'VERIFIED', disputable: false },
  { text: 'Hiring is now effectively frozen, with open roles at 2 against a 24-month baseline of 24.', n: 8, conf: 'VERIFIED', disputable: false },
];

export const aldermereDimensions: Dimension[] = [
  { name: 'LEADERSHIP', z: '+3.1', val: '2 exits /90d', base: '0.2', w: '.22', pct: 88, tick: 12 },
  { name: 'OPEN ROLES', z: '−3.3', val: '2 open', base: '24', w: '.15', pct: 92, tick: 78 },
  { name: 'HEADCOUNT', z: '−2.9', val: '−18% /qtr', base: '+2%', w: '.20', pct: 80, tick: 55 },
  { name: 'NEWS VOLUME', z: '+2.6', val: '14 items /30d', base: '3', w: '.13', pct: 74, tick: 18 },
  { name: 'LEGAL', z: '+2.4', val: '1 CCJ active', base: '0', w: '.18', pct: 66, tick: 8 },
  { name: 'SENTIMENT', z: '−2.2', val: '3.1 /5', base: '3.8', w: '.12', pct: 58, tick: 70 },
];

/** weekly composite scores Jan–Jul */
export const aldermereHist = [22, 23, 22, 24, 26, 25, 28, 31, 30, 34, 33, 38, 37, 42, 41, 48, 47, 53, 52, 58, 62, 61, 60, 66, 68, 71];

export const aldermereEventWeeks = [
  { n: 1, w: 9 },
  { n: 2, w: 12 },
  { n: 3, w: 14 },
  { n: 4, w: 17 },
  { n: 5, w: 19 },
  { n: 6, w: 21 },
  { n: 7, w: 23 },
  { n: 8, w: 25 },
];

export const evidenceData: EvidenceData = {
  audit1: {
    pct: '98.4',
    sub: '247 OF 251 CITATION MARKERS RESOLVE TO A DISTINCT FACTUAL CLAIM',
    body: 'Counts whether every [n] marker in generated narratives maps to exactly one claim and one signal. The 4 failures this quarter are listed in the write log below, unresolved and visible.',
  },
  audit2: {
    pct: '96.1',
    sub: 'SOURCE EXCERPT → CLAIM ENTAILMENT, SECOND-MODEL AUDIT LAYER',
    body: 'A separate model checks whether each cited excerpt actually entails the claim written against it. These two numbers are never merged — "zero hallucinations" is not a claim this product makes.',
  },
  headHash: '9f3c2e81…44a7d4',
  recordCount: 12847,
  chain: [
    { ts: '07-24 06:00', type: 'CAPTURE', desc: 'Daily capture — 8 vendors, 41 signals appended', hash: '9f3c…d4' },
    { ts: '07-23 14:12', type: 'SUPERSEDE', desc: 'Claim [5] Straitlace — annotated by E. Vance, score −3', hash: '8e2b…c1' },
    { ts: '07-23 06:00', type: 'CAPTURE', desc: 'Daily capture — 8 vendors, 38 signals appended', hash: '7d1a…b0' },
    { ts: '07-22 06:00', type: 'CAPTURE', desc: 'Daily capture — 8 vendors, 44 signals appended', hash: '6c09…9f' },
    { ts: '07-21 16:40', type: 'VERSION', desc: 'Prompt v12 promoted — recorded as chain event', hash: '5b98…8e' },
    { ts: '07-21 06:00', type: 'CAPTURE', desc: 'Daily capture — 8 vendors, 36 signals appended', hash: '4a87…7d' },
    { ts: '07-20 06:00', type: 'CAPTURE', desc: 'Daily capture — 7/8 (Ferrous source timeout, logged)', hash: '3976…6c' },
    { ts: '07-19 06:00', type: 'CAPTURE', desc: 'Daily capture — 8 vendors, 39 signals appended', hash: '2865…5b' },
  ],
  versions: { model: 'claude-sonnet-4-5', prompt: '#a41f…c2 · v12', since: '2026-06-02', auditModel: 'claude-haiku-4' },
  lastRun: {
    result: 'PASS',
    at: '2026-07-24 06:02 UTC',
    lines: ['12,847 / 12,847 LINKS INTACT', '0 REWRITES DETECTED · 0 GAPS', 'WALK TIME 3.2S'],
  },
};

export const methodologyData: MethodologyData = {
  leadBuckets: [
    { label: '0–15', n: 3 },
    { label: '15–30', n: 7 },
    { label: '30–45', n: 11 },
    { label: '45–60', n: 6 },
    { label: '60–90', n: 4 },
  ],
  medianDays: 41,
  stats: [
    { value: '41d', label: 'MEDIAN LEAD TIME' },
    { value: '7.7%', label: 'FALSE-POSITIVE RATE, CONTROL SET (4/52)' },
    { value: '29/31', label: 'EVENTS PRECEDED BY SCORE MOVEMENT' },
  ],
  weights: [
    { name: 'LEADERSHIP', v: 22 },
    { name: 'HEADCOUNT', v: 20 },
    { name: 'LEGAL', v: 18 },
    { name: 'OPEN ROLES', v: 15 },
    { name: 'NEWS VOLUME', v: 13 },
    { name: 'SENTIMENT', v: 12 },
  ],
  weightsNote:
    'Weights are the coefficients of a regularised logistic fit on the 31-event backtest, re-conditioned by vendor context (sector, size, listing status). They are re-fit quarterly; every re-fit is a chain event.',
  thresholdBody:
    'The threshold of 65 maximises F1 on the backtest: below it, false positives on control vendors exceed 15%; above it, median lead time drops under 30 days. The trade-off curve is reproducible from the chain.',
  thresholdTable: ['THRESHOLD 60 → FPR 15.4% · LEAD 48D', 'THRESHOLD 65 → FPR 7.7% · LEAD 41D ← SHIPPED', 'THRESHOLD 70 → FPR 3.8% · LEAD 26D'],
  thresholdNote: 'Orgs can move it — SETTINGS previews how many alerts a change would have fired historically before you commit.',
  limitations: [
    { num: 'L1', text: 'Public signals only. A vendor deteriorating silently — no filings, no press, no postings — will not move the score.' },
    { num: 'L2', text: 'Private-company coverage is tiered. Tier 2–3 vendors have thinner baselines; their z-scores carry wider error bands.' },
    { num: 'L3', text: 'Dimensions are not monotonic. Layoffs sometimes precede recovery; the model treats direction as context-dependent, imperfectly.' },
    { num: 'L4', text: 'News volume confounds with company size. Larger vendors generate more coverage; normalisation is approximate.' },
    { num: 'L5', text: 'The backtest is 31 events. Statistically useful, not statistically comfortable. Confidence intervals are published with it.' },
    { num: 'L6', text: 'Sentiment sources skew to English-language platforms and to employees who choose to review.' },
  ],
};

const itsFields: Record<string, Omit<RegisterRow, 'vendorId' | 'name' | 'state' | 'staleDays'>> = {
  aldermere: { lei: '2138…QX41', fn: 'F-DATA-02', contract: '2024-06 → 2027-06', law: 'ENG & WALES', subs: 'KESTREL · VERAPOINT', loc: 'UK · IE', subst: 'HARD', exit: 'YES · v3' },
  quarterpoint: { lei: '5299…MM18', fn: 'F-DATA-04', contract: '2025-01 → 2028-01', law: 'GERMANY', subs: 'AWS EU-C1', loc: 'DE', subst: 'MEDIUM', exit: 'YES · v1' },
  provene: { lei: '—', fn: 'F-KYC-01', contract: '2024-11 → 2026-11', law: 'ENG & WALES', subs: 'VERAPOINT · AWS', loc: 'UK', subst: 'HARD', exit: 'DRAFT' },
  straitlace: { lei: '5493…KP02', fn: 'F-PAY-01', contract: '2023-03 → 2026-09', law: 'NEW YORK', subs: 'KESTREL', loc: 'US · UK', subst: 'MEDIUM', exit: 'YES · v2' },
  ferrous: { lei: '—', fn: 'F-LOG-01', contract: '2025-05 → 2027-05', law: 'ENG & WALES', subs: 'OZANAM', loc: 'UK', subst: 'EASY', exit: 'YES · v1' },
  ozanam: { lei: '7245…BB77', fn: 'F-HOST-01', contract: '2022-08 → 2026-08', law: 'NETHERLANDS', subs: 'AWS EU-W1', loc: 'NL · IE', subst: 'MEDIUM', exit: 'YES · v4' },
  kestrel: { lei: '5493…AA10', fn: 'F-HOST-02', contract: '2021-02 → 2027-02', law: 'IRELAND', subs: 'NONE DECLARED', loc: 'IE · DE', subst: 'HARD', exit: 'YES · v5' },
  miravel: { lei: '—', fn: 'F-CX-01', contract: '2025-09 → 2026-09', law: 'ENG & WALES', subs: 'KESTREL · TWILION', loc: 'UK', subst: 'EASY', exit: 'NO' },
};

export const registerRows: RegisterRow[] = vendors.map((v) => ({
  vendorId: v.id,
  name: v.name,
  state: v.state,
  staleDays: v.staleDays,
  ...itsFields[v.id],
}));

export const registerChangelog: ChangelogEntry[] = [
  { ver: 'v14', date: '2026-07-08', desc: 'Aldermere substitutability re-assessed MEDIUM → HARD after Meridian contract report', by: 'E. VANCE' },
  { ver: 'v13', date: '2026-06-20', desc: 'Miravel CX added — F-CX-01, exit plan pending', by: 'A. OKAFOR' },
  { ver: 'v12', date: '2026-05-02', desc: 'Provene KYC exit plan moved to DRAFT, review scheduled Q3', by: 'E. VANCE' },
  { ver: 'v11', date: '2026-03-15', desc: 'Straitlace contract extension recorded, 2026-03 → 2026-09', by: 'A. OKAFOR' },
];

const compareCells: Record<string, { cloud: [string, 0 | 1 | 2]; region: [string, 0 | 1 | 2]; kyc: [string, 0 | 1 | 2]; sector: [string, 0 | 1 | 2] }> = {
  aldermere: { cloud: ['KESTREL', 2], region: ['EU-WEST', 2], kyc: ['VERAPOINT', 2], sector: ['DATA ENRICH.', 1] },
  quarterpoint: { cloud: ['AWS', 1], region: ['EU-CENTRAL', 0], kyc: ['—', 0], sector: ['DATA ENRICH.', 1] },
  provene: { cloud: ['AWS', 1], region: ['EU-WEST', 2], kyc: ['VERAPOINT', 2], sector: ['IDENTITY', 0] },
  straitlace: { cloud: ['KESTREL', 2], region: ['US-EAST', 0], kyc: ['—', 0], sector: ['PAYROLL', 0] },
  ferrous: { cloud: ['OZANAM', 0], region: ['EU-WEST', 2], kyc: ['—', 0], sector: ['LOGISTICS', 0] },
  ozanam: { cloud: ['AWS', 1], region: ['EU-WEST', 2], kyc: ['—', 0], sector: ['HOSTING', 1] },
  kestrel: { cloud: ['SELF', 0], region: ['EU-WEST', 2], kyc: ['—', 0], sector: ['HOSTING', 1] },
  miravel: { cloud: ['KESTREL', 2], region: ['EU-WEST', 2], kyc: ['—', 0], sector: ['CX', 0] },
};

export const compareRows: CompareRow[] = vendors.map((v) => {
  const c = compareCells[v.id];
  return {
    vendorId: v.id,
    name: v.name,
    score: v.score,
    cloud: { value: c.cloud[0], level: c.cloud[1] },
    region: { value: c.region[0], level: c.region[1] },
    kyc: { value: c.kyc[0], level: c.kyc[1] },
    sector: { value: c.sector[0], level: c.sector[1] },
  };
});

export const concentrationFindings: ConcentrationFinding[] = [
  { stat: '3 / 8', tone: 'amber', label: 'VENDORS RUN ON KESTREL CLOUD', body: 'Including Aldermere (ALERT). A Kestrel incident correlates three exposures — one of them already deteriorating.' },
  { stat: '6 / 8', tone: 'amber', label: 'CONCENTRATED IN EU-WEST', body: 'Region-level event (regulatory or infrastructural) touches six of eight monitored functions simultaneously.' },
  { stat: '2', tone: 'red', label: 'SHARE VERAPOINT FOR KYC', body: 'Aldermere and Provene both subcontract identity checks to Verapoint — a shared fourth party neither register surfaced until joined.' },
];

export const notificationChannels: NotificationChannel[] = [
  { id: 'slack', name: 'SLACK', target: '#vendor-risk' },
  { id: 'email', name: 'EMAIL', target: 'grc@meridian.co' },
  { id: 'webhook', name: 'WEBHOOK', target: 'archer bridge' },
];

/** threshold (nearest 5) → alerts that would have fired in the last 12 months */
export const backtestCurve: Record<number, number> = { 50: 31, 55: 22, 60: 16, 65: 9, 70: 5, 75: 3, 80: 2, 85: 1 };

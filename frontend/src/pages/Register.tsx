import { useEffect, useRef, useState } from 'react';
import ExportButton from '@/components/jobs/ExportButton';
import JobProgress from '@/components/jobs/JobProgress';
import RiskBadge from '@/components/risk/RiskBadge';
import StalenessChip from '@/components/risk/StalenessChip';
import { useRegister } from '@/lib/queries';

const GRID =
  'grid min-w-[1280px] grid-cols-[200px_130px_110px_150px_110px_140px_120px_90px_110px_120px] gap-3';

type JobState = 'idle' | 'running' | 'done';

export default function RegisterPage() {
  const { data } = useRegister();
  const [jobState, setJobState] = useState<JobState>('idle');
  const [jobPct, setJobPct] = useState(0);
  const [jobType, setJobType] = useState('');
  const iv = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => () => clearInterval(iv.current), []);

  if (!data) return null;

  const startJob = (type: string) => () => {
    if (jobState === 'running') return;
    setJobState('running');
    setJobPct(0);
    setJobType(type);
    iv.current = setInterval(() => {
      setJobPct((prev) => {
        const p = Math.min(100, prev + 7 + Math.random() * 9);
        if (p >= 100) {
          clearInterval(iv.current);
          setJobState('done');
          return 100;
        }
        return p;
      });
    }, 300);
  };

  const jobVisible = jobState !== 'idle';
  const jobDone = jobState === 'done';

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-20 pt-9">
      <div className="mb-[26px] flex items-end justify-between">
        <div>
          <div className="mb-2 font-mono text-[10px] tracking-[.2em] text-mute">REGISTER / ITS JOIN</div>
          <h1 className="mb-1.5 mt-0 text-[26px] font-semibold tracking-[-.01em]">
            Contract fields, joined to live signal.
          </h1>
          <p className="m-0 text-[13.5px] text-dim">
            Static columns are versioned (v14, changelog below). LIVE columns update on capture.
          </p>
        </div>
        <div className="flex gap-2.5">
          <ExportButton label="EXPORT ITS (XLSX)" variant="outline" onClick={startJob('ITS')} />
          <ExportButton label="EXPORT EVIDENCE PACK (PDF)" variant="primary" onClick={startJob('PDF')} />
        </div>
      </div>

      {jobVisible && <JobProgress jobType={jobType} pct={jobPct} done={jobDone} />}

      <div className="overflow-x-auto border border-line">
        <div className={`${GRID} border-b border-line px-[18px] py-3 font-mono text-[9px] tracking-[.14em] text-mute`}>
          <span>VENDOR</span>
          <span>LEI</span>
          <span>FUNCTION</span>
          <span>CONTRACT</span>
          <span>GOV. LAW</span>
          <span>SUBCONTRACTING</span>
          <span>DATA LOCATION</span>
          <span>SUBST.</span>
          <span>EXIT PLAN</span>
          <span className="text-risk-green">LIVE SIGNAL</span>
        </div>
        {data.rows.map((r) => (
          <div
            key={r.vendorId}
            className={`${GRID} items-center border-b border-line-row px-[18px] py-[13px] hover:bg-rowhover`}
          >
            <span className="text-[13px] font-medium">{r.name}</span>
            <span className="font-mono text-[10px] text-dim">{r.lei}</span>
            <span className="font-mono text-[10px] text-dim">{r.fn}</span>
            <span className="font-mono text-[10px] text-dim">{r.contract}</span>
            <span className="font-mono text-[10px] text-dim">{r.law}</span>
            <span className="font-mono text-[10px] text-dim">{r.subs}</span>
            <span className="font-mono text-[10px] text-dim">{r.loc}</span>
            <span className={`font-mono text-[10px] ${r.subst === 'HARD' ? 'text-risk-amber' : 'text-dim'}`}>
              {r.subst}
            </span>
            <span
              className={`font-mono text-[10px] ${r.exit === 'NO' || r.exit === 'DRAFT' ? 'text-risk-amber' : 'text-dim'}`}
            >
              {r.exit}
            </span>
            <div className="flex items-center gap-2">
              <RiskBadge state={r.state} />
              <StalenessChip days={r.staleDays} variant="compact" />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5 border border-line bg-panel">
        <div className="border-b border-line px-5 py-4 font-mono text-[10px] tracking-[.16em] text-mute">
          VERSION CHANGELOG — REGISTER IS VERSIONED, NEVER OVERWRITTEN
        </div>
        {data.changelog.map((c) => (
          <div key={c.ver} className="flex items-baseline gap-5 border-b border-line-row px-5 py-[13px]">
            <span className="w-20 font-mono text-[10.5px] text-dim">{c.ver}</span>
            <span className="w-[100px] font-mono text-[10.5px] text-mute">{c.date}</span>
            <span className="flex-1 text-[12.5px] text-fg-mid">{c.desc}</span>
            <span className="font-mono text-[9.5px] text-faint">{c.by}</span>
          </div>
        ))}
      </div>
    </main>
  );
}

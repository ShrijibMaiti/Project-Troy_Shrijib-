import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import ExportButton from '@/components/jobs/ExportButton';
import JobProgress from '@/components/jobs/JobProgress';
import RiskBadge from '@/components/risk/RiskBadge';
import StalenessChip from '@/components/risk/StalenessChip';
import ContractExtractDialog from '@/components/register/ContractExtractDialog';
import { useRegister } from '@/lib/queries';
import { runExport, downloadExport } from '@/lib/api';

const GRID =
  'grid min-w-[1280px] grid-cols-[200px_130px_110px_150px_110px_140px_120px_90px_110px_120px_90px] gap-3';

type JobState = 'idle' | 'running' | 'done';

export default function RegisterPage() {
  const { data } = useRegister();
  const qc = useQueryClient();
  const [extractFor, setExtractFor] = useState<{ id: string; name: string } | null>(null);
  const [jobState, setJobState] = useState<JobState>('idle');
  const [jobPct, setJobPct] = useState(0);
  const [jobType, setJobType] = useState('');
  const [artifactId, setArtifactId] = useState<string | null>(null);
  const [artifactName, setArtifactName] = useState('');
  const [contentHash, setContentHash] = useState('');

  if (!data) return null;

  const startJob = (type: string) => async () => {
    if (jobState === 'running') return;
    setJobState('running');
    setJobPct(30);
    setJobType(type);
    setArtifactId(null);
    try {
      const r = await runExport(type === 'PDF' ? 'pdf' : 'its');
      setArtifactId(r.artifactId);
      setArtifactName(r.filename);
      setContentHash(r.contentHash);
      setJobPct(100);
      setJobState('done');
    } catch (e) {
      console.error('export failed', e);
      setJobState('idle');
    }
  };

  const handleDownload = () => {
    if (artifactId) downloadExport(artifactId, artifactName || 'troy-export');
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

      {jobVisible && (
        <JobProgress
          jobType={jobType}
          pct={jobPct}
          done={jobDone}
          contentHash={contentHash}
          onDownload={handleDownload}
        />
      )}

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
          <span className="text-risk-blue">CONTRACT</span>
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
            <button
              onClick={() => setExtractFor({ id: r.vendorId, name: r.name })}
              className="cursor-pointer rounded-sm border border-line-3 bg-transparent px-2 py-1 font-mono text-[9px] tracking-[.08em] text-dim hover:border-mute hover:text-fg"
            >
              {r.contract === '—' ? 'EXTRACT' : 'RE-EXTRACT'}
            </button>
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

      {extractFor && (
        <ContractExtractDialog
          vendorId={extractFor.id}
          vendorName={extractFor.name}
          open={true}
          onClose={() => setExtractFor(null)}
          onSaved={() => qc.invalidateQueries({ queryKey: ['register'] })}
        />
      )}
    </main>
  );
}
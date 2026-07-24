import { scoreColorClass } from '@/lib/format';
import type { CompareCell, CompareRow } from '@/types/api';

const CELL_LEVELS = [
  'text-mute',
  'bg-tint-blue-cell text-dim',
  'bg-tint-blue-panel text-tint-blue-text border-l border-tint-blue-active',
];

function Cell({ cell }: { cell: CompareCell }) {
  return (
    <span className={`px-3 py-[13px] font-mono text-[10px] tracking-[.04em] ${CELL_LEVELS[cell.level]}`}>
      {cell.value}
    </span>
  );
}

interface Props {
  rows: CompareRow[];
}

/** Concentration-risk matrix: shared dependencies tint darker the more vendors sit on them. */
export default function ComparisonMatrix({ rows }: Props) {
  return (
    <div className="mb-5 border border-line bg-panel">
      <div className="grid grid-cols-[220px_repeat(4,1fr)_110px] border-b border-line">
        <span className="px-5 py-3.5 font-mono text-[9.5px] tracking-[.14em] text-mute">VENDOR</span>
        <span className="px-3 py-3.5 font-mono text-[9.5px] tracking-[.14em] text-mute">CLOUD</span>
        <span className="px-3 py-3.5 font-mono text-[9.5px] tracking-[.14em] text-mute">REGION</span>
        <span className="px-3 py-3.5 font-mono text-[9.5px] tracking-[.14em] text-mute">KYC SUB-PROC.</span>
        <span className="px-3 py-3.5 font-mono text-[9.5px] tracking-[.14em] text-mute">SECTOR</span>
        <span className="px-5 py-3.5 text-right font-mono text-[9.5px] tracking-[.14em] text-mute">SCORE</span>
      </div>
      {rows.map((r) => (
        <div key={r.vendorId} className="grid grid-cols-[220px_repeat(4,1fr)_110px] items-stretch border-b border-line-row">
          <span className="px-5 py-[13px] text-[13px] font-medium">{r.name}</span>
          <Cell cell={r.cloud} />
          <Cell cell={r.region} />
          <Cell cell={r.kyc} />
          <Cell cell={r.sector} />
          <span className={`px-5 py-[13px] text-right font-mono text-xs ${scoreColorClass(r.score)}`}>{r.score}</span>
        </div>
      ))}
      <div className="px-5 py-3.5 font-mono text-[9.5px] tracking-[.05em] text-faint">
        TINTED CELLS = SHARED DEPENDENCY. DARKER = MORE VENDORS CONCENTRATED ON IT.
      </div>
    </div>
  );
}

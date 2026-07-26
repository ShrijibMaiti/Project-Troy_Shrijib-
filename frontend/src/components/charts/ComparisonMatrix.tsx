import { scoreColorClass } from '@/lib/format';
import type { CompareCell, CompareRow } from '@/types/api';

const GRID = 'grid grid-cols-[220px_repeat(4,1fr)_110px]';

const CELL_LEVELS = [
  'text-mute',
  'bg-tint-blue-cell text-dim',
  'bg-tint-blue-panel text-tint-blue-text',
];

/** Column divider — faint, present on every cell so structure reads even when few cells are tinted. */
const DIVIDER = 'border-l border-line-row';

function Cell({ cell }: { cell: CompareCell }) {
  return (
    <span
      className={`px-3 py-[13px] font-mono text-[10px] tracking-[.04em] ${DIVIDER} ${CELL_LEVELS[cell.level]}`}
    >
      {cell.value}
    </span>
  );
}

interface Props {
  rows: CompareRow[];
}

/** Concentration-risk matrix: shared dependencies tint darker the more vendors sit on them. */
export default function ComparisonMatrix({ rows }: Props) {
  const head = 'px-3 py-3.5 font-mono text-[9.5px] tracking-[.14em] text-mute';

  return (
    <div className="mb-5 border border-line bg-panel">
      <div className={`${GRID} border-b border-line`}>
        <span className="px-5 py-3.5 font-mono text-[9.5px] tracking-[.14em] text-mute">VENDOR</span>
        <span className={`${head} ${DIVIDER}`}>CLOUD</span>
        <span className={`${head} ${DIVIDER}`}>REGION</span>
        <span className={`${head} ${DIVIDER}`}>KYC SUB-PROC.</span>
        <span className={`${head} ${DIVIDER}`}>SECTOR</span>
        <span className={`px-5 py-3.5 text-right font-mono text-[9.5px] tracking-[.14em] text-mute ${DIVIDER}`}>
          SCORE
        </span>
      </div>

      {rows.map((r) => (
        <div key={r.vendorId} className={`${GRID} items-stretch border-b border-line-row`}>
          <span className="px-5 py-[13px] text-[13px] font-medium">{r.name}</span>
          <Cell cell={r.cloud} />
          <Cell cell={r.region} />
          <Cell cell={r.kyc} />
          <Cell cell={r.sector} />
          <span className={`px-5 py-[13px] text-right font-mono text-xs ${DIVIDER} ${scoreColorClass(r.score)}`}>
            {r.score}
          </span>
        </div>
      ))}

      <div className="px-5 py-3.5 font-mono text-[9.5px] tracking-[.05em] text-faint">
        TINTED CELLS = SHARED DEPENDENCY. DARKER = MORE VENDORS CONCENTRATED ON IT.
      </div>
    </div>
  );
}
interface Props {
  jobType: string;
  pct: number;
  done: boolean;
  contentHash?: string;
  onDownload?: () => void;
}

export default function JobProgress({ jobType, pct, done, contentHash, onDownload }: Props) {
  const shortHash = contentHash ? `${contentHash.slice(0, 8)}…${contentHash.slice(-6)}` : '';
  return (
    <div className="mb-[18px] flex items-center gap-[18px] border border-tint-blue-border2 bg-tint-blue-bg2 px-5 py-3.5">
      <span className="font-mono text-[10px] tracking-[.12em] text-risk-blue">
        {done
          ? `${jobType} EXPORT — ${shortHash} · FROZEN & ON CHAIN`
          : `RENDERING — ${jobType} EXPORT (CONTENT-ADDRESSED, IMMUTABLE)`}
      </span>
      <div className="h-1 flex-1 bg-line-row">
        <div className="h-full bg-risk-blue transition-[width] duration-300" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-[11px] text-dim">{Math.round(pct)}%</span>
      {done && (
        <span
          onClick={onDownload}
          className="cursor-pointer border border-tint-green-border px-3 py-[5px] font-mono text-[10px] tracking-[.1em] text-risk-green hover:bg-tint-green-bg"
        >
          DOWNLOAD ↓
        </span>
      )}
    </div>
  );
}
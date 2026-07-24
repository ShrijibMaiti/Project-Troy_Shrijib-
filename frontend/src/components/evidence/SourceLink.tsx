interface Props {
  /** truncated row hash rendered alongside the dual link */
  hash: string;
}

/** Live + Wayback dual source link with the signal's row hash — every signal renders one. */
export default function SourceLink({ hash }: Props) {
  return (
    <div className="flex items-center gap-3">
      <span className="cursor-pointer border-b border-tint-blue-border font-mono text-[9.5px] text-risk-blue">
        LIVE ↗
      </span>
      <span className="cursor-pointer border-b border-tint-blue-border font-mono text-[9.5px] text-risk-blue">
        WAYBACK ↗
      </span>
      <span className="font-mono text-[9px] text-faint">{hash}</span>
    </div>
  );
}

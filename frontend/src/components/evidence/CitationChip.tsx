import { useState } from 'react';

interface Props {
  n: number;
  active: boolean;
  /** source signal fields for the hover preview */
  date: string;
  source: string;
  excerpt: string;
  onLocate: (n: number) => void;
}

/** Inline [n] citation marker: hover previews the source excerpt, click locates the signal in the timeline. */
export default function CitationChip({ n, active, date, source, excerpt, onLocate }: Props) {
  const [hover, setHover] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        onClick={() => onLocate(n)}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        className={`cursor-pointer rounded-sm border border-tint-blue-border px-1.5 py-px align-[2px] font-mono text-[10.5px] hover:border-risk-blue hover:text-fg ${
          active ? 'bg-tint-blue-active text-fg' : 'bg-tint-blue-bg text-risk-blue'
        }`}
      >
        [{n}]
      </button>
      {hover && (
        <span className="absolute left-0 top-6 z-40 block w-[300px] border border-line-3 bg-line-row px-[15px] py-[13px] shadow-[0_8px_30px_rgba(0,0,0,.6)]">
          <span className="mb-[7px] block font-mono text-[9px] tracking-[.12em] text-mute">
            {date} · {source.toUpperCase()}
          </span>
          <span className="block text-xs italic leading-relaxed text-fg-mid">"{excerpt}"</span>
        </span>
      )}
    </span>
  );
}

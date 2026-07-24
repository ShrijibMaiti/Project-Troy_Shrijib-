import type { Dimension } from '@/types/api';

export default function DimensionBars({ dims }: { dims: Dimension[] }) {
  return (
    <>
      {dims.map((d) => {
        const zAbs = Math.abs(parseFloat(d.z.replace('−', '-')));
        return (
          <div key={d.name} className="mb-4">
            <div className="mb-1.5 flex justify-between">
              <span className="font-mono text-[10.5px] tracking-[.08em] text-fg-mid">{d.name}</span>
              <span className={`font-mono text-[10.5px] ${zAbs >= 2.8 ? 'text-risk-red' : 'text-risk-amber'}`}>
                z {d.z}
              </span>
            </div>
            <div className="relative h-2 border border-line bg-line-row">
              <div
                className="absolute bottom-0 left-0 top-0"
                style={{ width: `${d.pct}%`, background: 'linear-gradient(90deg,#3A2226,#E5484D)' }}
              />
              <div className="absolute -bottom-[3px] -top-[3px] w-0.5 bg-fg" style={{ left: `${d.tick}%` }} />
            </div>
            <div className="mt-[5px] flex justify-between">
              <span className="font-mono text-[9px] text-mute">{d.val.toUpperCase()}</span>
              <span className="font-mono text-[9px] text-faint">
                BASE {d.base} · W {d.w}
              </span>
            </div>
          </div>
        );
      })}
    </>
  );
}

import LeadTimeChart from '@/components/charts/LeadTimeChart';
import { useMethodology } from '@/lib/queries';

export default function Methodology() {
  const { data } = useMethodology();
  if (!data) return null;
  const maxWeight = Math.max(...data.weights.map((w) => w.v));

  return (
    <main className="mx-auto max-w-[1100px] px-7 pb-20 pt-9">
      <div className="mb-2 font-mono text-[10px] tracking-[.2em] text-mute">METHODOLOGY / PUBLIC</div>
      <h1 className="mb-2 mt-0 text-[26px] font-semibold tracking-[-.01em]">
        How the score is built — and what it can't see.
      </h1>
      <p className="mb-10 mt-0 max-w-[680px] text-sm leading-relaxed text-dim">
        Nothing on this page is hidden behind a sales call. Weights, derivation, backtest and limitations, as shipped.
      </p>

      <div className="mb-5 border border-line bg-panel px-[30px] py-7">
        <div className="mb-2 flex items-baseline justify-between">
          <div className="font-mono text-[10px] tracking-[.16em] text-mute">
            THE BACKTEST — LEAD TIME BEFORE DOCUMENTED DETERIORATION EVENTS
          </div>
          <span className="font-mono text-[10px] text-mute">N=31 EVENTS · 2019–2025 · 52 CONTROLS</span>
        </div>
        <div className="grid grid-cols-[1fr_260px] items-end gap-9">
          <LeadTimeChart buckets={data.leadBuckets} medianDays={data.medianDays} height={240} />
          <div className="flex flex-col gap-[18px] pb-5">
            {data.stats.map((st) => (
              <div key={st.label}>
                <div className="font-mono text-[34px] font-semibold">{st.value}</div>
                <div className="font-mono text-[10px] tracking-[.1em] text-dim">{st.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-5">
        <div className="border border-line bg-panel px-[26px] py-6">
          <div className="mb-[18px] font-mono text-[10px] tracking-[.16em] text-mute">
            DIMENSION WEIGHTS — FITTED, NOT ASSERTED
          </div>
          {data.weights.map((w) => (
            <div key={w.name} className="mb-3 flex items-center gap-3.5">
              <span className="w-[150px] font-mono text-[10.5px] tracking-[.08em] text-fg-mid">{w.name}</span>
              <div className="h-2 flex-1 border border-line bg-line-row">
                <div className="h-full bg-risk-green" style={{ width: `${(w.v / maxWeight) * 100}%` }} />
              </div>
              <span className="w-[34px] text-right font-mono text-[11px]">.{w.v}</span>
            </div>
          ))}
          <p className="mb-0 mt-4 text-[12.5px] leading-[1.65] text-dim">{data.weightsNote}</p>
        </div>
        <div className="border border-line bg-panel px-[26px] py-6">
          <div className="mb-[18px] font-mono text-[10px] tracking-[.16em] text-mute">
            ALERT THRESHOLD — DERIVED, NOT CHOSEN
          </div>
          <p className="mb-3.5 mt-0 text-[13.5px] leading-[1.7] text-fg-mid">{data.thresholdBody}</p>
          <div className="font-mono text-[10.5px] leading-loose tracking-[.04em] text-dim">
            {data.thresholdTable.map((t) => (
              <div key={t}>{t}</div>
            ))}
          </div>
          <p className="mb-0 mt-3.5 text-[12.5px] leading-[1.65] text-dim">{data.thresholdNote}</p>
        </div>
      </div>

      <div className="border border-tint-amber-border bg-tint-amber-bg2 px-[30px] py-[26px]">
        <div className="mb-5 font-mono text-[10px] tracking-[.16em] text-risk-amber">
          STATED LIMITATIONS — READ BEFORE RELYING ON THE SCORE
        </div>
        <div className="grid grid-cols-2 gap-x-10 gap-y-3.5">
          {data.limitations.map((l) => (
            <div key={l.num} className="flex items-baseline gap-3.5">
              <span className="flex-none font-mono text-[10px] text-risk-amber">{l.num}</span>
              <p className="m-0 text-[13px] leading-relaxed text-fg-mid">{l.text}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

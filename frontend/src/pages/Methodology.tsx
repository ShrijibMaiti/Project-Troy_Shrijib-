import BacktestSeriesChart from '@/components/charts/BacktestSeriesChart';
import { useMethodology } from '@/lib/queries';

export default function Methodology() {
  const { data } = useMethodology();
  if (!data) return null;

  const maxWeight = data.weights.length ? Math.max(...data.weights.map((w) => w.v)) : 1;

  const stats = [
    { value: String(data.eventsTested), label: 'FAILURE CASES TESTED' },
    { value: String(data.controls), label: 'CONTROL VENDORS' },
    {
      value: data.leadDays === null ? 'n/a' : `${data.leadDays}d`,
      label: data.leadDays === 0 ? 'LEAD TIME — COINCIDENT, NOT LEADING' : 'LEAD TIME BEFORE FAILURE',
      warn: data.leadDays === 0,
    },
    {
      value: data.controlFpRate ?? 'not measured',
      label: 'FALSE-POSITIVE RATE, CONTROL SET',
      warn: !data.controlFpRate,
    },
  ];

  return (
    <main className="mx-auto max-w-[1100px] px-7 pb-20 pt-9">
      <div className="mb-2 font-mono text-[10px] tracking-[.2em] text-mute">METHODOLOGY / PUBLIC</div>
      <h1 className="mb-2 mt-0 text-[26px] font-semibold tracking-[-.01em]">
        How the score is built — and what it can't see.
      </h1>
      <p className="mb-10 mt-0 max-w-[680px] text-sm leading-relaxed text-dim">
        Nothing on this page is hidden behind a sales call. Weights, derivation, backtest and limitations, as
        shipped — including where the evidence is currently weak.
      </p>

      {/* ---- Backtest ---- */}
      <div className="mb-5 border border-line bg-panel px-[30px] py-7">
        <div className="mb-4 flex items-baseline justify-between">
          <div className="font-mono text-[10px] tracking-[.16em] text-mute">
            THE BACKTEST — COMPOSITE SCORE, FAILURE CASE vs CONTROL
          </div>
          <span className="font-mono text-[10px] tracking-[.08em] text-risk-amber">
            {data.status.replace(/_/g, ' ').toUpperCase()}
          </span>
        </div>

        <div className="grid grid-cols-[1fr_240px] items-start gap-9">
          <div>
            <BacktestSeriesChart
              series={data.series}
              failedName={data.failedName}
              controlName={data.controlName}
              failureDate={data.failureDate}
            />
            <div className="mt-2 flex gap-5 font-mono text-[9.5px] tracking-[.06em] text-dim">
              <span className="flex items-center gap-2">
                <span className="inline-block h-[2px] w-4 bg-risk-red" /> {data.failedName} — FAILED
              </span>
              <span className="flex items-center gap-2">
                <span className="inline-block h-[2px] w-4 bg-risk-amber" /> {data.controlName} — CONTROL
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-4 pt-2">
            {stats.map((st) => (
              <div key={st.label}>
                <div className={`font-mono text-[26px] font-semibold ${st.warn ? 'text-risk-amber' : ''}`}>
                  {st.value}
                </div>
                <div className="font-mono text-[9.5px] leading-snug tracking-[.08em] text-dim">{st.label}</div>
              </div>
            ))}
          </div>
        </div>

        <p className="mb-0 mt-6 border-t border-line pt-5 text-[13px] leading-[1.7] text-fg-mid">
          {data.summary}
        </p>
      </div>

      {/* ---- Weights + thresholds ---- */}
      <div className="mb-5 grid grid-cols-2 gap-5">
        <div className="border border-line bg-panel px-[26px] py-6">
          <div className="mb-[18px] font-mono text-[10px] tracking-[.16em] text-mute">
            DIMENSION WEIGHTS
          </div>
          {data.weights.length ? (
            <>
              {data.weights.map((w) => (
                <div key={w.name} className="mb-3 flex items-center gap-3.5">
                  <span className="w-[150px] font-mono text-[10.5px] tracking-[.08em] text-fg-mid">{w.name}</span>
                  <div className="h-2 flex-1 border border-line bg-line-row">
                    <div className="h-full bg-risk-green" style={{ width: `${(w.v / maxWeight) * 100}%` }} />
                  </div>
                  <span className="w-[34px] text-right font-mono text-[11px]">{w.v}</span>
                </div>
              ))}
            </>
          ) : (
            <p className="m-0 text-[13px] leading-[1.7] text-risk-amber">
              <b>Not calibrated.</b> No fitted weights exist yet. The scoring engine currently produces
              per-dimension point scores without a regression-derived weighting, so every composite on this
              deployment is <b>provisional</b>. Fitting weights requires a materially larger event set than the
              one backtested below.
            </p>
          )}
        </div>

        <div className="border border-line bg-panel px-[26px] py-6">
          <div className="mb-[18px] font-mono text-[10px] tracking-[.16em] text-mute">ALERT THRESHOLD</div>
          {data.thresholds.length ? (
            <div className="font-mono text-[10.5px] leading-loose tracking-[.04em] text-dim">
              {data.thresholds.map((t) => (
                <div key={t.label}>
                  {t.label} → {t.value}
                </div>
              ))}
            </div>
          ) : (
            <p className="m-0 text-[13px] leading-[1.7] text-risk-amber">
              <b>Not derived.</b> A threshold should be chosen by maximising separation between failure cases
              and controls on a backtest. On the current single-case backtest the control peaks at{' '}
              <b>{data.peakControl ?? '—'}</b> against the failure case's <b>{data.peakFailed ?? '—'}</b> — the two
              do not separate, so no defensible threshold can be set from this data. The interface uses a
              provisional value of 65 for display only.
            </p>
          )}
        </div>
      </div>

      {/* ---- Limitations ---- */}
      <div className="border border-tint-amber-border bg-tint-amber-bg2 px-[30px] py-[26px]">
        <div className="mb-5 font-mono text-[10px] tracking-[.16em] text-risk-amber">
          STATED LIMITATIONS — READ BEFORE RELYING ON THE SCORE
        </div>
        <div className="grid grid-cols-2 gap-x-10 gap-y-3.5">
          {data.limitations.map((l, i) => (
            <div key={i} className="flex items-baseline gap-3.5">
              <span className="flex-none font-mono text-[10px] text-risk-amber">L{i + 1}</span>
              <p className="m-0 text-[13px] leading-relaxed text-fg-mid">{l}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 font-mono text-[9.5px] tracking-[.06em] text-faint">
        ENGINE {data.engineVersion} · CALIBRATION {data.calibrated ? 'LOADED' : 'ABSENT — SCORES PROVISIONAL'}
      </div>
    </main>
  );
}
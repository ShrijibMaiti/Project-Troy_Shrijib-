import ComparisonMatrix from '@/components/charts/ComparisonMatrix';
import { useCompare } from '@/lib/queries';

export default function Compare() {
  const { data } = useCompare();
  if (!data) return null;

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-20 pt-9">
      <div className="mb-2 font-mono text-[10px] tracking-[.2em] text-mute">COMPARE / CONCENTRATION RISK</div>
      <h1 className="mb-2 mt-0 text-[26px] font-semibold tracking-[-.01em]">Where the portfolio fails together.</h1>
      <p className="mb-[34px] mt-0 max-w-[640px] text-sm leading-relaxed text-dim">
        Shared sub-processors, region clustering and correlated score movement across the fleet. Cells link to the
        underlying register field or signal.
      </p>

      <ComparisonMatrix rows={data.rows} />

      <div className="grid grid-cols-3 gap-5">
        {data.findings.map((f) => (
          <div key={f.label} className="border border-line bg-panel px-6 py-[22px]">
            <div
              className={`mb-2 font-mono text-[26px] font-semibold ${
                f.tone === 'red' ? 'text-risk-red' : 'text-risk-amber'
              }`}
            >
              {f.stat}
            </div>
            <div className="mb-3 font-mono text-[10px] tracking-[.12em] text-dim">{f.label}</div>
            <p className="m-0 text-[12.5px] leading-relaxed text-dim">{f.body}</p>
          </div>
        ))}
      </div>
    </main>
  );
}

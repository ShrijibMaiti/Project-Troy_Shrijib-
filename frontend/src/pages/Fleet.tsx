import { useNavigate } from 'react-router-dom';
import TrendChart from '@/components/charts/TrendChart';
import RiskBadge from '@/components/risk/RiskBadge';
import StalenessChip from '@/components/risk/StalenessChip';
import { useAlerts, useVendors } from '@/lib/queries';
import { useUiStore, type FleetFilter } from '@/lib/store';
import { scoreColorClass, sparkColorHex } from '@/lib/format';

const FILTERS: FleetFilter[] = ['ALL', 'ALERTS', 'WATCH', 'STALE >7D'];

const GRID = 'grid grid-cols-[250px_90px_1fr_130px_130px_120px] gap-4';

export default function Fleet() {
  const navigate = useNavigate();
  const { data: vendors = [] } = useVendors();
  const { data: alerts = [] } = useAlerts();
  const { fleetFilter, setFleetFilter } = useUiStore();

  const active = vendors.filter((v) => !v.archived);
  const rows = active.filter((v) => {
    if (fleetFilter === 'ALERTS') return v.state === 'ALERT';
    if (fleetFilter === 'WATCH') return v.state === 'WATCH';
    if (fleetFilter === 'STALE >7D') return v.staleDays > 7;
    return true;
  });

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-20 pt-9">
      <div className="mb-[26px] flex items-baseline justify-between">
        <div>
          <div className="mb-2 font-mono text-[10px] tracking-[.2em] text-mute">FLEET / WORKLIST</div>
          <h1 className="m-0 text-[26px] font-semibold tracking-[-.01em]">{active.length} vendors monitored</h1>
        </div>
        <div className="font-mono text-[11px] tracking-[.06em] text-dim">
          LAST CAPTURE — TODAY 06:00 UTC · SUCCESS 8/8 · 312 SIGNALS ON CHAIN THIS WEEK
        </div>
      </div>

      <div className="mb-[30px] border border-tint-red-border bg-tint-red-bg2">
        <div className="border-b border-tint-red-line px-5 py-3.5 font-mono text-[10px] tracking-[.18em] text-risk-red">
          ▲ ACTIVE ALERTS — {alerts.length}
        </div>
        {alerts.map((a) => (
          <div
            key={a.vendorId}
            onClick={() => navigate(`/vendor/${a.vendorId}`)}
            className="flex cursor-pointer items-center gap-5 border-b border-tint-red-row px-5 py-4 hover:bg-tint-red-hover"
          >
            <RiskBadge state={a.state} />
            <span className="w-[230px] text-[15px] font-semibold">{a.name}</span>
            <span className="flex-1 font-mono text-xs text-dim">{a.reason}</span>
            <span className="font-mono text-xs text-risk-red">{a.scoreTxt}</span>
            <span className="font-mono text-[11px] text-mute">OPEN →</span>
          </div>
        ))}
      </div>

      <div className="mb-[18px] flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFleetFilter(f)}
            className={`cursor-pointer rounded-sm border px-3.5 py-[7px] font-mono text-[10px] tracking-[.1em] hover:border-mute ${
              fleetFilter === f ? 'border-mute bg-navactive text-fg' : 'border-line-2 bg-transparent text-dim'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="border border-line">
        <div className={`${GRID} border-b border-line px-5 py-3 font-mono text-[9.5px] tracking-[.16em] text-mute`}>
          <span>VENDOR</span>
          <span>SCORE</span>
          <span>90-DAY TREND</span>
          <span>LAST SIGNAL</span>
          <span>CAPTURE RATE</span>
          <span>TIER</span>
        </div>
        {rows.map((v) => (
          <div
            key={v.id}
            onClick={() => navigate(`/vendor/${v.id}`)}
            className={`${GRID} cursor-pointer items-center border-b border-line-row px-5 py-[15px] hover:bg-rowhover`}
          >
            <div className="flex items-center gap-3">
              <RiskBadge state={v.state} />
              <span className="text-[14.5px] font-medium">{v.name}</span>
            </div>
            <span className={`font-mono text-sm ${scoreColorClass(v.score)}`}>
              {v.pendingCapture ? '—' : v.score}
            </span>
            <TrendChart values={v.hist} stroke={sparkColorHex(v.state)} />
            <StalenessChip days={v.staleDays} pending={v.pendingCapture} />
            <span className={`font-mono text-xs ${v.captureRate < 90 ? 'text-risk-amber' : 'text-dim'}`}>
              {v.captureRate}%
            </span>
            <span className="font-mono text-[10px] tracking-[.1em] text-dim">{v.tier}</span>
          </div>
        ))}
      </div>
      <div className="mt-3.5 font-mono text-[10px] tracking-[.06em] text-faint">
        Scores update on capture; rows marked LIVE. Register and artifacts are versioned separately — see REGISTER.
      </div>
    </main>
  );
}

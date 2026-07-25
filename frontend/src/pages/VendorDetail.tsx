import { useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import ScoreDial from '@/components/risk/ScoreDial';
import Seismograph from '@/components/risk/Seismograph';
import DimensionBars from '@/components/risk/DimensionBars';
import StalenessChip from '@/components/risk/StalenessChip';
import ConfidenceBadge from '@/components/evidence/ConfidenceBadge';
import DisputeDialog from '@/components/evidence/DisputeDialog';
import SourceLink from '@/components/evidence/SourceLink';
import NarrativeView from '@/components/narrative/NarrativeView';
import { useAppendSupersede, useVendorDetail } from '@/lib/queries';
import { useUiStore } from '@/lib/store';

const ALERT_THRESHOLD = 65;

export default function VendorDetail() {
  const { id } = useParams();
  const { data } = useVendorDetail(id);
  const { activeSignal, setActiveSignal } = useUiStore();
  const appendSupersede = useAppendSupersede();

  const [disputeN, setDisputeN] = useState(0);
  const [toastRecord, setToastRecord] = useState(0);

  const timelineRef = useRef<HTMLDivElement>(null);
  const signalRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();

  if (!id) return <div className="p-8 font-mono text-mute">No vendor selected — return to Fleet.</div>;
  if (!data) return null;
  const { vendor, signals, narrative, dimensions, hist, eventWeeks, scoreDelta90d, artifactMeta } = data;

  const locateSignal = (n: number) => {
    setActiveSignal(n);
    const el = signalRefs.current[n];
    const box = timelineRef.current;
    if (el && box) box.scrollTo({ top: el.offsetTop - box.offsetTop - 12, behavior: 'smooth' });
  };

  const disputedClaim = narrative.find((sn) => sn.n === disputeN);
  const disputedSignal = signals.find((sig) => sig.n === disputeN);
  const disputeDelta = 0; // real delta comes back in the dispute response

  const submitDispute = (annotation: string) => {
    const claimN = disputeN;
    setDisputeN(0);
    appendSupersede.mutate(
      { claimN, vendorName: vendor.name, annotation, scoreDelta: 0, signalId: disputedSignal?.id /* see note */ },
      {
        onSuccess: ({ recordNumber }) => {
          setToastRecord(recordNumber);
          clearTimeout(toastTimer.current);
          toastTimer.current = setTimeout(() => setToastRecord(0), 4000);
        },
      },
    );
  };

  return (
    <main className="mx-auto max-w-[1400px] px-7 pb-20 pt-[30px]">
      <div className="mb-[22px] flex items-center gap-3.5">
        <Link to="/fleet" className="font-mono text-[11px] tracking-[.1em] text-dim hover:text-fg">
          ← FLEET
        </Link>
        <span className="text-line-2">/</span>
        <h1 className="m-0 text-[22px] font-semibold tracking-[-.01em]">{vendor.name}</h1>
        <span className={`rounded-sm border px-[9px] py-1 font-mono text-[9.5px] tracking-[.14em] ${
          vendor.state === 'ALERT' ? 'border-tint-red-border bg-tint-red-bg text-risk-red'
          : vendor.state === 'WATCH' ? 'border-tint-amber-border bg-tint-amber-bg text-risk-amber'
          : 'border-line-2 text-dim'
        }`}>
          {vendor.state}
        </span>
        <span className="rounded-sm border border-line-2 px-[9px] py-1 font-mono text-[9.5px] tracking-[.1em] text-dim">
          {vendor.tier}
        </span>
        <StalenessChip days={vendor.staleDays} variant="header" />
        <span className="ml-auto font-mono text-[9.5px] tracking-[.1em] text-risk-green">
          ● LIVE — UPDATES ON CAPTURE
        </span>
      </div>

      <div className="mb-5 grid grid-cols-[180px_1fr] gap-5">
        <div className="flex flex-col items-center justify-center border border-line bg-panel p-5">
          <ScoreDial score={vendor.score} />
          <div className="mt-2.5 font-mono text-[10px] tracking-[.08em] text-risk-red">{scoreDelta90d}</div>
          <button
            onClick={() => timelineRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
            className="mt-2 cursor-pointer border-b border-line-2 bg-transparent pb-0.5 font-mono text-[9px] tracking-[.1em] text-mute hover:text-dim"
          >
            SOURCE: 6 DIMENSIONS ↓
          </button>
        </div>
        <div className="border border-line bg-panel px-6 pb-3 pt-5">
          <div className="mb-2.5 flex justify-between">
            <span className="font-mono text-[10px] tracking-[.16em] text-mute">
              SEISMOGRAPH — COMPOSITE SCORE, JAN–JUL 2026 · EVENT MARKERS ARE CLICKABLE
            </span>
            <span className="font-mono text-[10px] text-mute">ALERT THRESHOLD {ALERT_THRESHOLD}</span>
          </div>
          <Seismograph
            hist={hist}
            eventWeeks={eventWeeks}
            activeSignal={activeSignal}
            threshold={ALERT_THRESHOLD}
            onMarkerClick={locateSignal}
          />
          <div className="mt-1.5 font-mono text-[9.5px] tracking-[.05em] text-faint">
            Every visible spike maps to a dated signal. Click a marker to locate it in the timeline.
          </div>
        </div>
      </div>

      <div className="grid grid-cols-[340px_1fr_320px] items-start gap-5">
        {/* Signal timeline */}
        <div className="flex max-h-[640px] flex-col border border-line bg-panel">
          <div className="border-b border-line px-[18px] py-4 font-mono text-[10px] tracking-[.16em] text-mute">
            SIGNAL TIMELINE — {signals.length} OF 214 · APPEND-ONLY
          </div>
          <div ref={timelineRef} className="flex-1 overflow-y-auto">
            {signals.map((sig) => (
              <div
                key={sig.n}
                ref={(el) => (signalRefs.current[sig.n] = el)}
                onClick={() => setActiveSignal(sig.n)}
                className={`cursor-pointer border-b border-line-row py-4 pl-4 pr-[18px] transition-colors duration-300 ${
                  activeSignal === sig.n ? 'border-l-2 border-l-risk-blue bg-tint-blue-panel' : 'border-l-2 border-l-transparent'
                }`}
              >
                <div className="mb-[7px] flex justify-between">
                  <span className="font-mono text-[10px] tracking-[.08em] text-dim">
                    {sig.date} · [{sig.n}]
                  </span>
                  <ConfidenceBadge conf={sig.conf} />
                </div>
                <div className="mb-[5px] text-[13px] font-semibold">{sig.title}</div>
                <div className="mb-[9px] text-xs leading-[1.55] text-dim">{sig.excerpt}</div>
                <SourceLink hash={sig.hash} />
              </div>
            ))}
          </div>
        </div>

        {/* Narrative */}
        <NarrativeView
          narrative={narrative}
          signals={signals}
          activeSignal={activeSignal}
          artifactMeta={artifactMeta}
          onLocate={locateSignal}
          onDispute={setDisputeN}
        />

        {/* Decomposition */}
        <div className="flex flex-col gap-3.5">
          <div className="border border-line bg-panel px-5 py-[18px]">
            <div className="mb-4 font-mono text-[10px] tracking-[.16em] text-mute">
              DECOMPOSITION — VALUE · BASELINE · Z
            </div>
            <DimensionBars dims={dimensions} />
            <div className="font-mono text-[9px] leading-relaxed tracking-[.04em] text-faint">
              Tick = vendor's own 24-month baseline. Weights are context-conditioned — derivation on METHODOLOGY.
            </div>
          </div>
        </div>
      </div>

      <DisputeDialog
        open={disputeN > 0}
        claimN={disputeN}
        claimText={disputedClaim?.text ?? ''}
        score={vendor.score}
        scoreDelta={disputeDelta}
        onClose={() => setDisputeN(0)}
        onSubmit={submitDispute}
      />

      {toastRecord > 0 && (
        <div className="fixed bottom-7 right-7 z-[120] border border-tint-green-border bg-tint-green-bg px-5 py-4 shadow-[0_10px_40px_rgba(0,0,0,.6)]">
          <div className="mb-1.5 font-mono text-[10.5px] tracking-[.1em] text-risk-green">
            SUPERSEDE RECORD WRITTEN — #{toastRecord.toLocaleString('en-US')}
          </div>
          <div className="font-mono text-[9.5px] tracking-[.04em] text-dim">
            Score recomputes on next capture. Original claim remains on chain.
          </div>
        </div>
      )}
    </main>
  );
}
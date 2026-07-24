import { useEffect, useRef, useState } from 'react';
import HashChainStatus from '@/components/evidence/HashChainStatus';
import { useEvidence } from '@/lib/queries';

export default function Evidence() {
  const { data } = useEvidence();
  const [verifying, setVerifying] = useState(false);
  const [verifyStep, setVerifyStep] = useState(-1);
  const [verified, setVerified] = useState(false);
  const iv = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => () => clearInterval(iv.current), []);

  if (!data) return null;
  const { audit1, audit2, headHash, chain, versions, lastRun, recordCount } = data;
  const records = recordCount.toLocaleString('en-US');

  const startVerify = () => {
    if (verifying) return;
    setVerifying(true);
    setVerified(false);
    setVerifyStep(-1);
    let step = -1;
    iv.current = setInterval(() => {
      step++;
      if (step >= chain.length) {
        clearInterval(iv.current);
        setVerifying(false);
        setVerified(true);
        setVerifyStep(chain.length);
      } else {
        setVerifyStep(step);
      }
    }, 260);
  };

  const auditCard = (label: string, a: typeof audit1) => (
    <div className="border border-line bg-panel px-7 py-[26px]">
      <div className="mb-[18px] font-mono text-[10px] tracking-[.16em] text-mute">{label}</div>
      <div className="font-mono text-[56px] font-semibold leading-none tracking-[-.02em]">
        {a.pct}
        <span className="text-[26px] text-mute">%</span>
      </div>
      <div className="mb-4 mt-3 font-mono text-[11px] text-dim">{a.sub}</div>
      <p className="m-0 text-[13px] leading-[1.65] text-dim">{a.body}</p>
    </div>
  );

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-20 pt-9">
      <div className="mb-2 font-mono text-[10px] tracking-[.2em] text-mute">EVIDENCE / AUDIT TRAIL</div>
      <h1 className="mb-2 mt-0 text-[26px] font-semibold tracking-[-.01em]">
        The audit trail is a property of the system, not a claim about it.
      </h1>
      <p className="mb-[34px] mt-0 max-w-[680px] text-sm leading-relaxed text-dim">
        Two audit numbers, published separately — never combined into a single reassuring figure. A hash-chained store
        you can verify from this screen.
      </p>

      <div className="mb-5 grid grid-cols-2 gap-5">
        {auditCard('AUDIT 01 — NARRATIVE RESOLUTION', audit1)}
        {auditCard('AUDIT 02 — EXTRACTION FIDELITY', audit2)}
      </div>

      <div className="grid grid-cols-[1fr_380px] items-start gap-5">
        <div className="border border-line bg-panel">
          <HashChainStatus
            records={records}
            headHash={headHash}
            verifying={verifying}
            verified={verified}
            verifyStep={verifyStep}
            total={chain.length}
            onVerify={startVerify}
          />
          <div>
            {chain.map((r, i) => {
              const checked = verified || (verifying && verifyStep >= i);
              const walking = verifying && verifyStep === i;
              return (
                <div
                  key={i}
                  className={`flex items-center gap-4 border-b border-line-row px-[22px] py-3 transition-colors ${
                    walking ? 'bg-tint-green-bg' : ''
                  }`}
                >
                  <span
                    className={`w-4 flex-none font-mono text-xs ${checked ? 'text-risk-green' : 'text-faint'} ${
                      walking ? 'animate-pulse2' : ''
                    }`}
                  >
                    {checked ? '✓' : walking ? '·' : '○'}
                  </span>
                  <span className="w-[120px] font-mono text-[11px] text-dim">{r.ts}</span>
                  <span
                    className={`w-[90px] font-mono text-[10px] tracking-[.08em] ${
                      r.type === 'SUPERSEDE' ? 'text-risk-amber' : r.type === 'VERSION' ? 'text-risk-blue' : 'text-mute'
                    }`}
                  >
                    {r.type}
                  </span>
                  <span className="flex-1 text-[12.5px] text-fg-mid">{r.desc}</span>
                  <span className="font-mono text-[9.5px] text-faint">{r.hash}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="flex flex-col gap-3.5">
          <div className="border border-line bg-panel px-[22px] py-5">
            <div className="mb-4 font-mono text-[10px] tracking-[.16em] text-mute">GENERATION VERSIONS — LIVE</div>
            <div className="flex flex-col gap-3">
              {(
                [
                  ['MODEL', versions.model],
                  ['PROMPT', versions.prompt],
                  ['SINCE', versions.since],
                  ['AUDIT MODEL', versions.auditModel],
                ] as const
              ).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="font-mono text-[11px] text-dim">{k}</span>
                  <span className="font-mono text-[11px]">{v}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 font-mono text-[9px] leading-relaxed tracking-[.04em] text-faint">
              Every artifact records the pair that produced it. Version changes are chain events.
            </div>
          </div>
          <div className="border border-line bg-panel px-[22px] py-5">
            <div className="mb-4 font-mono text-[10px] tracking-[.16em] text-mute">LAST VERIFICATION RUN</div>
            <div className="mb-2.5 flex items-center gap-2.5">
              <span className="font-mono text-[13px] text-risk-green">{lastRun.result}</span>
              <span className="font-mono text-[10.5px] text-mute">{lastRun.at}</span>
            </div>
            <div className="font-mono text-[10px] leading-[1.8] text-dim">
              {lastRun.lines.map((l) => (
                <div key={l}>{l}</div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

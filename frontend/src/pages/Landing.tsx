import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import LeadTimeChart from '@/components/charts/LeadTimeChart';
import { methodologyData } from '@/data/fixtures';

const FLAP_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

function FlapRow({ target, offset, tick }: { target: string; offset: number; tick: number }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {target.split('').map((ch, i) => {
        if (ch === ' ') return <span key={i} className="inline-block h-[84px] w-[26px]" />;
        const settleAt = offset + i * 2 + 6;
        const settled = tick >= settleAt;
        const show = settled ? ch : FLAP_CHARS[(tick * 7 + i * 13) % FLAP_CHARS.length];
        return (
          <span
            key={i}
            className={`relative inline-flex h-[84px] w-[58px] items-center justify-center rounded border border-line-2 font-mono text-[44px] font-medium shadow-[0_2px_0_rgba(0,0,0,.5)] ${
              settled ? 'animate-flapIn text-fg' : 'text-mute'
            }`}
            style={{ background: 'linear-gradient(180deg,#17171A 0%,#141416 49%,#101012 51%,#131315 100%)' }}
          >
            {show}
          </span>
        );
      })}
    </div>
  );
}

const MONO_LINK = 'font-mono text-[11px] tracking-[.12em] text-dim hover:text-fg';
const KICKER = 'mb-11 font-mono text-[11px] tracking-[.2em] text-mute';

export default function Landing() {
  const [tick, setTick] = useState(0);
  const [cross, setCross] = useState({ x: -1, y: -1 });
  const [demoEmail, setDemoEmail] = useState('');
  const [demoSent, setDemoSent] = useState(false);

  useEffect(() => {
    let t = 0;
    const iv = setInterval(() => {
      t++;
      setTick(t);
      if (t > 70) clearInterval(iv);
    }, 55);
    return () => clearInterval(iv);
  }, []);

  const showCross = cross.x >= 0;

  const decayCols = [
    { day: 'DAY 0', color: 'text-risk-green', label: 'ONBOARDING', body: 'The questionnaire is answered, the register is accurate, the contract is signed. Everything you know about this vendor is true — today.' },
    { day: 'DAY 182', color: 'text-risk-amber', label: 'SILENT DECAY', body: 'The CFO left. Engineering postings dried up. A court filing landed. None of it is in your register, because nothing asked.' },
    { day: 'DAY 365', color: 'text-risk-red', label: 'THE NEXT CYCLE', body: 'The annual questionnaire finally catches up — months after the deterioration began, and long after you could have acted early.' },
  ];

  const notItems = [
    { title: 'Not a security rating', body: 'BitSight and SecurityScorecard scan attack surface. Troy reads business-health signals: filings, leadership, headcount, sentiment, litigation.' },
    { title: 'Not a questionnaire platform', body: 'OneTrust and Prevalent run assessment workflow. Troy is what happens between their cycles — it attaches to your register, it doesn’t replace it.' },
    { title: 'Not onboarding or contracts', body: 'Due diligence, contract management and exit planning stay where they are. Troy joins its live signal to those records; it doesn’t own them.' },
    { title: 'Not an unaccountable model', body: 'Every AI-written sentence renders with its citation inline. Two audit numbers are published — never a "zero hallucinations" claim.' },
  ];

  const steps = [
    { num: '01', name: 'CAPTURE', body: 'Daily automated capture of public signals per vendor — filings, postings, press, sentiment — each write appended to a hash-chained store.' },
    { num: '02', name: 'SCORE', body: 'Six dimensions scored against each vendor’s own baseline. Context-conditioned weights; z-scores, not vibes.' },
    { num: '03', name: 'NARRATE', body: 'An analyst narrative is generated with a citation on every factual sentence, pinned to model and prompt version.' },
    { num: '04', name: 'PROVE', body: 'Every claim resolves to a dated source — live URL plus archive snapshot — one click away. Disputes supersede; nothing is ever edited.' },
  ];

  const claims = [
    { num: '01', text: 'An evidence pack that attaches to your register — not a register, and not a replacement for one.' },
    { num: '02', text: 'Two audit numbers, published separately: narrative-resolution rate and extraction-fidelity rate. Never a combined "zero hallucinations" figure.' },
    { num: '03', text: 'Staleness is shown, not hidden. If the last signal is six days old, the screen says so in amber.' },
    { num: '04', text: 'Corrections supersede and annotate. The store is append-only; nothing is edited, nothing is deleted.' },
    { num: '05', text: 'Public-signal coverage only. Private-company depth is tiered, and the tier is labelled on every vendor.' },
    { num: '06', text: 'The backtest — lead time and false-positive rate — is published with its limitations, on a page anyone can read.' },
  ];

  return (
    <div className="min-h-screen bg-ink">
      <nav className="sticky top-0 z-50 flex h-16 items-center justify-between border-b border-line bg-ink/90 px-10 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[15px] font-semibold tracking-[.18em]">TROY</span>
          <span className="font-mono text-[10px] tracking-[.12em] text-mute">VENDOR RISK / EVIDENCE</span>
        </div>
        <div className="flex items-center gap-7">
          <Link to="/methodology" className={MONO_LINK}>
            METHODOLOGY
          </Link>
          <Link to="/signin" className={MONO_LINK}>
            SIGN IN
          </Link>
          <Link
            to="/fleet"
            className="rounded-sm bg-fg px-[18px] py-[9px] font-mono text-[11px] tracking-[.12em] !text-ink hover:bg-white"
          >
            REQUEST DEMO
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="mx-auto max-w-[1360px] border-b border-line px-10 pb-[90px] pt-[110px]">
        <div className="mb-9 flex items-center gap-2.5">
          <span className="h-[7px] w-[7px] animate-blink rounded-full bg-risk-green" />
          <span className="font-mono text-[11px] tracking-[.2em] text-dim">
            CONTINUOUS VENDOR MONITORING — EVIDENCE FIRST
          </span>
        </div>
        <div className="mb-10 flex flex-col gap-2.5">
          <FlapRow target="WE WATCH THE" offset={0} tick={tick} />
          <FlapRow target="364 DAYS BETWEEN" offset={10} tick={tick} />
        </div>
        <p className="mb-9 mt-0 max-w-[620px] text-lg leading-[1.65] text-dim">
          We don't replace your register or your security rating. Troy watches vendors in the gap between questionnaire
          cycles — and proves every word of what it tells you. No number appears without its source reachable in one
          click.
        </p>
        <div className="flex gap-3.5">
          <Link
            to="/fleet"
            className="rounded-sm bg-fg px-[26px] py-3.5 font-mono text-xs tracking-[.12em] !text-ink hover:bg-white"
          >
            OPEN THE CONSOLE →
          </Link>
          <Link
            to="/evidence"
            className="rounded-sm border border-line-3 px-[26px] py-3.5 font-mono text-xs tracking-[.12em] text-fg hover:border-mute"
          >
            SEE THE EVIDENCE SCREEN
          </Link>
        </div>
      </section>

      {/* 01 Decay */}
      <section className="border-b border-line">
        <div className="mx-auto max-w-[1360px] px-10 py-20">
          <div className={KICKER}>01 / THE DECAY PROBLEM</div>
          <div className="grid grid-cols-3 gap-px border border-line bg-line">
            {decayCols.map((d) => (
              <div key={d.day} className="bg-ink px-8 pb-10 pt-9">
                <div className={`mb-1.5 font-mono text-[52px] tracking-[-.02em] ${d.color}`}>{d.day}</div>
                <div className="mb-[18px] font-mono text-[11px] tracking-[.16em] text-dim">{d.label}</div>
                <p className="m-0 text-[14.5px] leading-[1.65] text-dim">{d.body}</p>
              </div>
            ))}
          </div>
          <p className="mb-0 mt-7 font-mono text-xs tracking-[.06em] text-mute">Troy exists for days 1–364.</p>
        </div>
      </section>

      {/* 02 What Troy is not */}
      <section className="border-b border-line">
        <div className="mx-auto max-w-[1360px] px-10 py-20">
          <div className={KICKER}>02 / WHAT TROY IS NOT</div>
          <div className="grid grid-cols-2 gap-px border border-line bg-line">
            {notItems.map((n) => (
              <div key={n.title} className="flex items-baseline gap-[18px] bg-ink px-8 py-[30px]">
                <span className="flex-none font-mono text-[13px] text-risk-red">✕</span>
                <div>
                  <div className="mb-1.5 text-[15px] font-semibold">{n.title}</div>
                  <div className="text-[13.5px] leading-relaxed text-dim">{n.body}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 03 How it works (crosshair) */}
      <section
        className="relative overflow-hidden border-b border-line"
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setCross({ x: e.clientX - r.left, y: e.clientY - r.top });
        }}
        onMouseLeave={() => setCross({ x: -1, y: -1 })}
      >
        {showCross && (
          <>
            <div
              className="pointer-events-none absolute bottom-0 top-0 z-[2] w-px bg-[rgba(230,228,223,.12)]"
              style={{ left: cross.x }}
            />
            <div
              className="pointer-events-none absolute left-0 right-0 z-[2] h-px bg-[rgba(230,228,223,.12)]"
              style={{ top: cross.y }}
            />
            <div
              className="pointer-events-none absolute z-[2] font-mono text-[9.5px] tracking-[.08em] text-mute"
              style={{ left: cross.x + 10, top: cross.y + 10 }}
            >
              X {Math.round(cross.x)} · Y {Math.round(cross.y)}
            </div>
          </>
        )}
        <div className="relative mx-auto max-w-[1360px] px-10 py-20">
          <div className={KICKER}>03 / HOW IT WORKS</div>
          <div className="grid grid-cols-4 gap-px border border-line bg-line">
            {steps.map((st) => (
              <div key={st.num} className="min-h-[180px] bg-ink px-7 pb-[42px] pt-[34px] hover:bg-field">
                <div className="mb-[22px] font-mono text-[11px] text-mute">{st.num}</div>
                <div className="mb-3.5 font-mono text-base tracking-[.14em]">{st.name}</div>
                <p className="m-0 text-[13.5px] leading-relaxed text-dim">{st.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 04 Backtest */}
      <section className="border-b border-line">
        <div className="mx-auto grid max-w-[1360px] grid-cols-2 items-center gap-16 px-10 py-20">
          <div>
            <div className="mb-7 font-mono text-[11px] tracking-[.2em] text-mute">04 / THE BACKTEST</div>
            <h2 className="mb-5 mt-0 text-[34px] font-semibold leading-tight tracking-[-.01em]">
              The score moved a median of{' '}
              <span className="border-b-2 border-risk-green font-mono">41 days</span> before real deterioration events.
            </h2>
            <p className="mb-5 mt-0 text-[15px] leading-[1.65] text-dim">
              Backtested against 31 documented vendor deterioration events, 2019–2025. False-positive rate on control
              vendors: 7.7%. Full derivation, thresholds and stated limitations are public on the Methodology page —
              including what the score can't see.
            </p>
            <Link
              to="/methodology"
              className="border-b border-line-3 pb-[3px] font-mono text-[11px] tracking-[.12em] text-dim hover:text-fg"
            >
              READ THE METHODOLOGY →
            </Link>
          </div>
          <div className="border border-line bg-panel p-7">
            <div className="mb-5 font-mono text-[10px] tracking-[.16em] text-mute">
              LEAD TIME BEFORE EVENT — DAYS (N=31)
            </div>
            <LeadTimeChart
              buckets={methodologyData.leadBuckets}
              medianDays={methodologyData.medianDays}
              height={200}
              medianLabel="MEDIAN 41D"
            />
          </div>
        </div>
      </section>

      {/* 05 Claims discipline */}
      <section className="border-b border-line">
        <div className="mx-auto max-w-[1360px] px-10 py-20">
          <div className={KICKER}>05 / CLAIMS DISCIPLINE</div>
          <div className="grid grid-cols-2 gap-x-16">
            {claims.map((c) => (
              <div key={c.num} className="flex items-baseline gap-4 border-b border-line py-[22px]">
                <span className="flex-none font-mono text-[11px] text-risk-green">{c.num}</span>
                <p className="m-0 text-[14.5px] leading-relaxed text-fg-mid">{c.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 06 Demo */}
      <section className="border-b border-line">
        <div className="mx-auto max-w-[820px] px-10 py-[90px] text-center">
          <div className="mb-6 font-mono text-[11px] tracking-[.2em] text-mute">06 / REQUEST A DEMO</div>
          <h2 className="mb-9 mt-0 text-[30px] font-semibold tracking-[-.01em]">See your own vendors through it.</h2>
          {demoSent ? (
            <div className="border border-tint-green-border bg-tint-green-bg p-5 font-mono text-[13px] tracking-[.06em] text-risk-green">
              REQUEST LOGGED — WE'LL REPLY WITHIN ONE BUSINESS DAY.
            </div>
          ) : (
            <div className="flex justify-center gap-2.5">
              <input
                value={demoEmail}
                onChange={(e) => setDemoEmail(e.target.value)}
                placeholder="work email"
                className="w-80 rounded-sm border border-line-3 bg-field px-4 py-3.5 font-mono text-[13px] text-fg outline-none focus:border-mute"
              />
              <button
                onClick={() => setDemoSent(true)}
                className="cursor-pointer rounded-sm border-none bg-fg px-6 py-3.5 font-mono text-xs tracking-[.12em] text-ink hover:bg-white"
              >
                REQUEST →
              </button>
            </div>
          )}
        </div>
      </section>

      <footer className="mx-auto max-w-[1360px] px-10 pb-10 pt-[70px]">
        <svg viewBox="0 0 900 150" className="mb-[50px] block w-full">
          <text
            x="0"
            y="120"
            fontFamily="Sometype Mono"
            fontSize="150"
            fontWeight="600"
            letterSpacing="30"
            fill="none"
            stroke="#26262B"
            strokeWidth="1.5"
            className="animate-dashDraw [stroke-dasharray:1200]"
          >
            TROY
          </text>
        </svg>
        <div className="flex flex-wrap items-baseline justify-between gap-4 border-t border-line pt-[26px]">
          <span className="font-mono text-[10.5px] tracking-[.12em] text-mute">
            © 2026 TROY SYSTEMS — AN EVIDENCE PACK, NOT A REGISTER.
          </span>
          <div className="flex gap-[26px]">
            <Link to="/methodology" className="font-mono text-[10.5px] tracking-[.12em] text-mute hover:text-fg">
              METHODOLOGY
            </Link>
            <Link to="/evidence" className="font-mono text-[10.5px] tracking-[.12em] text-mute hover:text-fg">
              AUDIT TRAIL
            </Link>
            <Link to="/signin" className="font-mono text-[10.5px] tracking-[.12em] text-mute hover:text-fg">
              SIGN IN
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

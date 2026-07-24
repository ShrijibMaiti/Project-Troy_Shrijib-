import { useNavigate } from 'react-router-dom';

export default function SignIn() {
  const navigate = useNavigate();
  const goFleet = () => navigate('/fleet');

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink">
      <div className="w-[380px] border border-line bg-panel p-10">
        <div className="mb-1.5 font-mono text-base font-semibold tracking-[.18em]">TROY</div>
        <div className="mb-[34px] font-mono text-[10px] tracking-[.14em] text-mute">
          ORG-SCOPED ACCESS · ROLE-GATED ACTIONS
        </div>
        <div className="mb-[22px] flex flex-col gap-2.5">
          <input
            placeholder="work email"
            className="rounded-sm border border-line-3 bg-field px-3.5 py-[13px] font-mono text-[13px] text-fg outline-none focus:border-mute"
          />
          <button
            onClick={goFleet}
            className="cursor-pointer rounded-sm border-none bg-fg p-[13px] font-mono text-xs tracking-[.12em] text-ink hover:bg-white"
          >
            CONTINUE →
          </button>
        </div>
        <button
          onClick={goFleet}
          className="w-full cursor-pointer rounded-sm border border-line-3 bg-transparent p-3 font-mono text-[11px] tracking-[.1em] text-dim hover:border-mute hover:text-fg"
        >
          CONTINUE WITH SSO (MERIDIAN GRC)
        </button>
        <div className="mt-[26px] font-mono text-[9.5px] leading-[1.7] tracking-[.04em] text-faint">
          Disputes, exports and settings are gated by org role. Analyst · Reviewer · Admin.
        </div>
      </div>
    </div>
  );
}

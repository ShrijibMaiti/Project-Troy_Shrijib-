interface Props {
  /** formatted record count, e.g. "12,847" */
  records: string;
  headHash: string;
  verifying: boolean;
  verified: boolean;
  verifyStep: number;
  total: number;
  onVerify: () => void;
}

/** Head hash + verify button + walk state for the append-only chain panel. */
export default function HashChainStatus({ records, headHash, verifying, verified, verifyStep, total, onVerify }: Props) {
  return (
    <>
      <div className="flex items-center justify-between border-b border-line px-[22px] py-[18px]">
        <span className="font-mono text-[10px] tracking-[.16em] text-mute">
          HASH CHAIN — APPEND-ONLY SIGNAL STORE · {records} RECORDS
        </span>
        <button
          onClick={onVerify}
          className={`cursor-pointer rounded-sm border-none px-4 py-[9px] font-mono text-[10px] tracking-[.12em] text-ink hover:bg-white ${
            verifying ? 'bg-dim' : 'bg-fg'
          }`}
        >
          {verifying ? 'WALKING CHAIN…' : verified ? 'VERIFY AGAIN' : 'VERIFY CHAIN →'}
        </button>
      </div>
      <div className="flex items-center gap-6 border-b border-line px-[22px] py-[18px]">
        <span className="font-mono text-[10px] tracking-[.12em] text-mute">HEAD</span>
        <span className="font-mono text-[13px] tracking-[.04em] text-fg">{headHash}</span>
        <span
          className={`ml-auto font-mono text-[10px] tracking-[.1em] ${
            verified ? 'text-risk-green' : verifying ? 'text-risk-amber' : 'text-mute'
          }`}
        >
          {verifying
            ? `WALKING… ${verifyStep + 1}/${total} SHOWN`
            : verified
              ? `✓ CHAIN INTACT — ${records}/${records}`
              : 'UNVERIFIED THIS SESSION'}
        </span>
      </div>
    </>
  );
}

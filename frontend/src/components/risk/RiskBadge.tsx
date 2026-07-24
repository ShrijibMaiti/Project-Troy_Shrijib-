import type { VendorState } from '@/types/api';

const STYLES: Record<VendorState, string> = {
  ALERT: 'text-risk-red border-tint-red-border bg-tint-red-bg',
  WATCH: 'text-risk-amber border-tint-amber-border bg-tint-amber-bg',
  STABLE: 'text-risk-green border-tint-green-border bg-tint-green-bg',
};

export default function RiskBadge({ state }: { state: VendorState }) {
  return (
    <span
      className={`flex-none rounded-sm border px-[7px] py-[3px] font-mono text-[8.5px] tracking-[.12em] ${STYLES[state]}`}
    >
      {state}
    </span>
  );
}

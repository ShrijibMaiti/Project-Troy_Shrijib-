import { staleLabel } from '@/lib/format';

interface Props {
  days: number;
  /** vendor has not yet had a first capture run */
  pending?: boolean;
  /**
   * row     — fleet table cell chip (amber-boxed when stale)
   * header  — vendor-detail header chip ("◷ LAST SIGNAL 5D AGO")
   * compact — register table micro-label ("5D" / "TODAY")
   */
  variant?: 'row' | 'header' | 'compact';
}

const STALE_AFTER_DAYS = 4;

/** Capture staleness, surfaced by default wherever a vendor renders — staleness is the problem Troy sells against. */
export default function StalenessChip({ days, pending = false, variant = 'row' }: Props) {
  const stale = days > STALE_AFTER_DAYS;

  if (variant === 'header') {
    return (
      <span
        className={`rounded-sm px-[9px] py-1 font-mono text-[10px] ${
          stale ? 'border border-tint-amber-border bg-tint-amber-bg text-risk-amber' : 'border border-line-2 text-dim'
        }`}
      >
        ◷ LAST SIGNAL {days}D AGO
      </span>
    );
  }

  if (variant === 'compact') {
    return (
      <span className={`font-mono text-[9px] ${stale ? 'text-risk-amber' : 'text-mute'}`}>
        {days === 0 ? 'TODAY' : `${days}D`}
      </span>
    );
  }

  return (
    <span
      className={`w-fit rounded-sm px-2 py-[3px] font-mono text-[10px] tracking-[.06em] ${
        stale ? 'border border-tint-amber-border bg-tint-amber-bg text-risk-amber' : 'text-mute'
      }`}
    >
      {pending ? 'PENDING' : staleLabel(days)}
    </span>
  );
}

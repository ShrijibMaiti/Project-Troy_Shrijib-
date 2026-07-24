import type { Confidence } from '@/types/api';

const STYLES: Record<Confidence, string> = {
  VERIFIED: 'text-risk-green border-tint-green-border',
  REPORTED: 'text-risk-amber border-tint-amber-border',
  UNCONFIRMED: 'text-dim border-line-2',
};

interface Props {
  conf: Confidence;
  /** compact single-letter variant used inline in the narrative */
  small?: boolean;
}

export default function ConfidenceBadge({ conf, small }: Props) {
  return (
    <span
      className={`rounded-sm border px-1.5 py-0.5 align-[2px] font-mono tracking-[.1em] ${
        small ? 'text-[8px]' : 'text-[8.5px]'
      } ${STYLES[conf]}`}
    >
      {small ? conf.charAt(0) : conf}
    </span>
  );
}

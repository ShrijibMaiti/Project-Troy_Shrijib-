import { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';

const ALERT_THRESHOLD = 65;

interface Props {
  open: boolean;
  claimN: number;
  claimText: string;
  /** vendor's current composite score */
  score: number;
  /** estimated points removed if the claim is superseded (computed, per claim) */
  scoreDelta: number;
  onClose: () => void;
  onSubmit: (annotation: string) => void;
}

export default function DisputeDialog({ open, claimN, claimText, score, scoreDelta, onClose, onSubmit }: Props) {
  const [annotation, setAnnotation] = useState('');
  useEffect(() => {
    if (open) setAnnotation('');
  }, [open]);

  const newScore = score - scoreDelta;
  const dropsBelow = newScore < ALERT_THRESHOLD;

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[100] bg-[rgba(5,5,6,.75)] backdrop-blur-[3px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-[100] w-[560px] -translate-x-1/2 -translate-y-1/2 border border-line-3 bg-panel shadow-[0_20px_80px_rgba(0,0,0,.7)] focus:outline-none">
          <div className="flex items-center justify-between border-b border-line px-[26px] py-5">
            <Dialog.Title className="font-mono text-[11px] font-normal tracking-[.16em]">
              DISPUTE CLAIM [{claimN}]
            </Dialog.Title>
            <Dialog.Close className="cursor-pointer border-none bg-transparent font-mono text-sm text-mute hover:text-fg">
              ✕
            </Dialog.Close>
          </div>
          <div className="p-[26px] pt-6">
            <div className="mb-5 border border-line-2 bg-field px-4 py-3.5">
              <div className="mb-2 font-mono text-[9px] tracking-[.12em] text-mute">CLAIM UNDER DISPUTE</div>
              <div className="text-[13.5px] italic leading-relaxed text-fg-body">"{claimText}"</div>
            </div>
            <div className="mb-2 font-mono text-[9px] tracking-[.12em] text-mute">ANNOTATION (REQUIRED)</div>
            <textarea
              value={annotation}
              onChange={(e) => setAnnotation(e.target.value)}
              placeholder="Why this claim should be superseded — with a source if you have one."
              className="h-20 w-full resize-none rounded-sm border border-line-3 bg-field p-3 font-sans text-[13px] text-fg outline-none focus:border-mute"
            />
            <div className="my-5 flex items-center gap-4 border border-tint-blue-border2 bg-tint-blue-bg2 px-4 py-3.5">
              <span className="font-mono text-[9px] tracking-[.12em] text-risk-blue">SCORE IF SUPERSEDED</span>
              <span className="font-mono text-lg font-semibold">
                {score} → {newScore}
              </span>
              <span className={`font-mono text-[10px] ${dropsBelow ? 'text-risk-green' : 'text-risk-amber'}`}>
                −{scoreDelta} · {dropsBelow ? 'DROPS BELOW ALERT THRESHOLD' : 'REMAINS ABOVE ALERT THRESHOLD'}
              </span>
            </div>
            <div className="mb-5 font-mono text-[9.5px] leading-[1.7] tracking-[.04em] text-faint">
              This writes a SUPERSEDE record to the append-only store. The original claim remains on chain, marked
              superseded. Nothing is edited. Nothing is deleted.
            </div>
            <div className="flex justify-end gap-2.5">
              <button
                onClick={onClose}
                className="cursor-pointer rounded-sm border border-line-3 bg-transparent px-[18px] py-[11px] font-mono text-[10.5px] tracking-[.1em] text-dim hover:text-fg"
              >
                CANCEL
              </button>
              <button
                onClick={() => onSubmit(annotation.trim())}
                disabled={!annotation.trim()}
                className="cursor-pointer rounded-sm border-none bg-fg px-[18px] py-[11px] font-mono text-[10.5px] tracking-[.1em] text-ink hover:bg-white disabled:cursor-not-allowed disabled:opacity-45"
              >
                WRITE SUPERSEDE RECORD →
              </button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

import { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import type { Vendor } from '@/types/api';

const TIERS = ['PRIVATE·T1', 'PRIVATE·T2', 'PRIVATE·T3', 'PUBLIC·T1', 'PUBLIC·T2'];

interface Props {
  open: boolean;
  /** vendor being edited, or null when adding */
  vendor: Vendor | null;
  onClose: () => void;
  onSave: (fields: { name: string; tier: string }) => void;
}

export default function VendorFormDialog({ open, vendor, onClose, onSave }: Props) {
  const [name, setName] = useState('');
  const [tier, setTier] = useState(TIERS[0]);

  useEffect(() => {
    if (open) {
      setName(vendor?.name ?? '');
      setTier(vendor?.tier ?? TIERS[0]);
    }
  }, [open, vendor]);

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[100] bg-[rgba(5,5,6,.75)] backdrop-blur-[3px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-[100] w-[460px] -translate-x-1/2 -translate-y-1/2 border border-line-3 bg-panel shadow-[0_20px_80px_rgba(0,0,0,.7)] focus:outline-none">
          <div className="flex items-center justify-between border-b border-line px-[26px] py-5">
            <Dialog.Title className="font-mono text-[11px] font-normal tracking-[.16em]">
              {vendor ? `EDIT VENDOR — ${vendor.name.toUpperCase()}` : 'ADD VENDOR'}
            </Dialog.Title>
            <Dialog.Close className="cursor-pointer border-none bg-transparent font-mono text-sm text-mute hover:text-fg">
              ✕
            </Dialog.Close>
          </div>
          <div className="p-[26px] pt-6">
            <div className="mb-2 font-mono text-[9px] tracking-[.12em] text-mute">LEGAL NAME</div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="vendor legal name"
              className="mb-5 w-full rounded-sm border border-line-3 bg-field px-3.5 py-3 font-sans text-[13px] text-fg outline-none focus:border-mute"
            />
            <div className="mb-2 font-mono text-[9px] tracking-[.12em] text-mute">COVERAGE TIER</div>
            <select
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              className="mb-5 w-full cursor-pointer rounded-sm border border-line-3 bg-field px-3 py-3 font-mono text-[11px] tracking-[.08em] text-fg outline-none focus:border-mute"
            >
              {TIERS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <div className="mb-5 font-mono text-[9.5px] leading-[1.7] tracking-[.04em] text-faint">
              {vendor
                ? 'Config changes are logged as chain events. Signal history is untouched.'
                : 'Capture starts on the next 06:00 UTC run. Score and baseline populate as signals land.'}
            </div>
            <div className="flex justify-end gap-2.5">
              <button
                onClick={onClose}
                className="cursor-pointer rounded-sm border border-line-3 bg-transparent px-[18px] py-[11px] font-mono text-[10.5px] tracking-[.1em] text-dim hover:text-fg"
              >
                CANCEL
              </button>
              <button
                onClick={() => onSave({ name: name.trim(), tier })}
                disabled={!name.trim()}
                className="cursor-pointer rounded-sm border-none bg-fg px-[18px] py-[11px] font-mono text-[10.5px] tracking-[.1em] text-ink hover:bg-white disabled:cursor-not-allowed disabled:opacity-45"
              >
                {vendor ? 'SAVE CHANGES →' : 'ADD VENDOR →'}
              </button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

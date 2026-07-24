import { useState } from 'react';
import VendorFormDialog from '@/components/settings/VendorFormDialog';
import { useAddVendor, useSetVendorArchived, useUpdateVendor, useVendors } from '@/lib/queries';
import { useUiStore } from '@/lib/store';
import { backtestCurve, notificationChannels } from '@/data/fixtures';
import type { Vendor } from '@/types/api';

export default function Settings() {
  const { data: vendors = [] } = useVendors();
  const { threshold, setThreshold, channels, toggleChannel } = useUiStore();
  const addVendor = useAddVendor();
  const updateVendor = useUpdateVendor();
  const setArchived = useSetVendorArchived();

  /** null = closed, 'new' = add form, Vendor = edit form */
  const [form, setForm] = useState<'new' | Vendor | null>(null);
  const active = vendors.filter((v) => !v.archived);
  const archived = vendors.filter((v) => v.archived);

  const saveForm = (fields: { name: string; tier: string }) => {
    if (form === 'new') addVendor.mutate(fields);
    else if (form) updateVendor.mutate({ id: form.id, patch: fields });
    setForm(null);
  };

  const nearest = Math.max(50, Math.min(85, Math.round(threshold / 5) * 5));
  const thresholdAlerts = backtestCurve[nearest];
  const alertsColor =
    thresholdAlerts > 15 ? 'text-risk-red' : thresholdAlerts > 9 ? 'text-risk-amber' : 'text-risk-green';
  const thresholdNote =
    threshold < 65 ? 'LOWER = EARLIER BUT NOISIER' : threshold > 65 ? 'HIGHER = QUIETER BUT LATER' : 'AS SHIPPED';

  return (
    <main className="mx-auto max-w-[1100px] px-7 pb-20 pt-9">
      <div className="mb-2 font-mono text-[10px] tracking-[.2em] text-mute">SETTINGS / ADMIN</div>
      <h1 className="mb-[34px] mt-0 text-[26px] font-semibold tracking-[-.01em]">Configuration</h1>
      <div className="mb-5 grid grid-cols-2 gap-5">
        <div className="border border-line bg-panel">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <span className="font-mono text-[10px] tracking-[.16em] text-mute">MONITORED VENDORS</span>
            <button
              onClick={() => setForm('new')}
              className="cursor-pointer rounded-sm border-none bg-fg px-3.5 py-[7px] font-mono text-[10px] tracking-[.1em] text-ink hover:bg-white"
            >
              + ADD VENDOR
            </button>
          </div>
          {active.map((v) => (
            <div key={v.id} className="flex items-center gap-3.5 border-b border-line-row px-5 py-3">
              <span className="flex-1 text-[13px] font-medium">{v.name}</span>
              {v.pendingCapture && (
                <span className="rounded-sm border border-tint-amber-border bg-tint-amber-bg px-2 py-0.5 font-mono text-[8.5px] tracking-[.1em] text-risk-amber">
                  PENDING FIRST CAPTURE
                </span>
              )}
              <span className="font-mono text-[9.5px] tracking-[.08em] text-mute">{v.tier}</span>
              <button
                onClick={() => setForm(v)}
                className="cursor-pointer rounded-sm border border-line-2 bg-transparent px-2.5 py-1 font-mono text-[9px] tracking-[.08em] text-mute hover:border-mute hover:text-fg"
              >
                EDIT
              </button>
              <button
                onClick={() => setArchived.mutate({ id: v.id, archived: true })}
                className="cursor-pointer rounded-sm border border-line-2 bg-transparent px-2.5 py-1 font-mono text-[9px] tracking-[.08em] text-mute hover:border-tint-amber-border hover:text-risk-amber"
              >
                ARCHIVE
              </button>
            </div>
          ))}
          {archived.length > 0 && (
            <>
              <div className="border-b border-line-row px-5 pb-2 pt-4 font-mono text-[9px] tracking-[.16em] text-faint">
                ARCHIVED — CAPTURE STOPPED, CHAIN RETAINED
              </div>
              {archived.map((v) => (
                <div key={v.id} className="flex items-center gap-3.5 border-b border-line-row px-5 py-3 opacity-60">
                  <span className="flex-1 text-[13px] font-medium text-dim">{v.name}</span>
                  <span className="rounded-sm border border-line-2 px-2 py-0.5 font-mono text-[8.5px] tracking-[.1em] text-mute">
                    ARCHIVED
                  </span>
                  <span className="font-mono text-[9.5px] tracking-[.08em] text-mute">{v.tier}</span>
                  <button
                    onClick={() => setArchived.mutate({ id: v.id, archived: false })}
                    className="cursor-pointer rounded-sm border border-line-2 bg-transparent px-2.5 py-1 font-mono text-[9px] tracking-[.08em] text-mute hover:border-tint-green-border hover:text-risk-green"
                  >
                    RESTORE
                  </button>
                </div>
              ))}
            </>
          )}
          <div className="px-5 py-3.5 font-mono text-[9px] leading-relaxed tracking-[.05em] text-faint">
            Archiving stops capture but keeps the chain. Vendor history is never deleted.
          </div>
        </div>
        <div className="flex flex-col gap-5">
          <div className="border border-line bg-panel px-[22px] py-5">
            <div className="mb-[18px] font-mono text-[10px] tracking-[.16em] text-mute">NOTIFICATION CHANNELS</div>
            {notificationChannels.map((c) => {
              const on = channels[c.id];
              return (
                <div key={c.id} className="flex items-center gap-3.5 border-b border-line-row py-[11px]">
                  <button
                    onClick={() => toggleChannel(c.id)}
                    className={`relative h-[18px] w-[34px] flex-none cursor-pointer rounded-[9px] border p-0 ${
                      on ? 'border-tint-green-border bg-tint-green-bg' : 'border-line-2 bg-field'
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 h-3 w-3 rounded-full transition-[left] duration-150 ${
                        on ? 'left-[18px] bg-risk-green' : 'left-0.5 bg-faint'
                      }`}
                    />
                  </button>
                  <span className="flex-1 font-mono text-[11px] tracking-[.06em]">{c.name}</span>
                  <span className="font-mono text-[10px] text-mute">{c.target}</span>
                </div>
              );
            })}
          </div>
          <div className="border border-line bg-panel px-[22px] py-5">
            <div className="mb-1.5 font-mono text-[10px] tracking-[.16em] text-mute">
              ALERT THRESHOLD — WHAT-IF PREVIEW
            </div>
            <p className="mb-[18px] mt-0 text-[12.5px] leading-relaxed text-dim">
              Move the threshold; Troy replays the last 12 months before you commit.
            </p>
            <div className="mb-4 flex items-center gap-4">
              <input
                type="range"
                min={50}
                max={85}
                value={threshold}
                onChange={(e) => setThreshold(parseInt(e.target.value, 10))}
                className="flex-1 accent-fg"
              />
              <span className="w-11 text-right font-mono text-xl font-semibold">{threshold}</span>
            </div>
            <div className="flex items-center justify-between border border-line-2 bg-field px-[18px] py-4">
              <span className="font-mono text-[10.5px] tracking-[.06em] text-dim">WOULD HAVE FIRED, LAST 12 MO</span>
              <span className={`font-mono text-[22px] font-semibold ${alertsColor}`}>{thresholdAlerts} ALERTS</span>
            </div>
            <div className="mt-3 font-mono text-[9.5px] tracking-[.05em] text-faint">
              SHIPPED DEFAULT 65 → 9 ALERTS · {thresholdNote}
            </div>
            <button className="mt-3.5 w-full cursor-pointer rounded-sm border border-line-3 bg-transparent p-2.5 font-mono text-[10px] tracking-[.1em] text-fg hover:border-mute">
              COMMIT THRESHOLD (LOGGED AS CHAIN EVENT)
            </button>
          </div>
        </div>
      </div>
      <VendorFormDialog
        open={form !== null}
        vendor={form === 'new' ? null : form}
        onClose={() => setForm(null)}
        onSave={saveForm}
      />
    </main>
  );
}

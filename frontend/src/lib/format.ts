import type { VendorState } from '@/types/api';

export const scoreColorClass = (n: number) =>
  n >= 65 ? 'text-risk-red' : n >= 40 ? 'text-risk-amber' : 'text-dim';

export const scoreColorHex = (n: number) => (n >= 65 ? '#E5484D' : n >= 40 ? '#D9A13B' : '#8A8A93');

export const sparkColorHex = (state: VendorState) =>
  state === 'ALERT' ? '#E5484D' : state === 'WATCH' ? '#D9A13B' : '#55555C';

export const staleLabel = (days: number) => (days === 0 ? 'TODAY' : `${days}D AGO`);

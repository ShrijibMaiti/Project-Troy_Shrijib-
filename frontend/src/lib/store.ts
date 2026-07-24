import { create } from 'zustand';

export type FleetFilter = 'ALL' | 'ALERTS' | 'WATCH' | 'STALE >7D';

interface UiState {
  fleetFilter: FleetFilter;
  setFleetFilter: (f: FleetFilter) => void;
  /** signal [n] highlighted across seismograph, narrative chips and timeline */
  activeSignal: number;
  setActiveSignal: (n: number) => void;
  threshold: number;
  setThreshold: (t: number) => void;
  channels: Record<string, boolean>;
  toggleChannel: (id: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  fleetFilter: 'ALL',
  setFleetFilter: (fleetFilter) => set({ fleetFilter }),
  activeSignal: 0,
  setActiveSignal: (activeSignal) => set({ activeSignal }),
  threshold: 65,
  setThreshold: (threshold) => set({ threshold }),
  channels: { slack: true, email: true, webhook: false },
  toggleChannel: (id) =>
    set((s) => ({ channels: { ...s.channels, [id]: !s.channels[id] } })),
}));

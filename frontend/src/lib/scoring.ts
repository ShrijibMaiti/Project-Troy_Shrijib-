import type { Dimension, Signal } from '@/types/api';

/**
 * Mock stand-in for the scoring engine's supersede recompute: estimates how many
 * composite points a signal contributes via the dimension it feeds, as
 * weight × |z| × SCALE. The real engine replays the CDC diff without the
 * superseded signal; until it exists, SCALE is calibrated so the flagship
 * disputed claim ([5], NEWS VOLUME) matches the designed prototype value (−7).
 * The point of this function is that the diff is derived from fixture data —
 * dispute a different claim and the number changes.
 */
const SCALE = 20.7;

export function estimateSupersedeImpact(signal: Signal, dims: Dimension[]): number {
  const d = dims.find((x) => x.name === signal.dim);
  if (!d) return 1;
  const z = Math.abs(parseFloat(d.z.replace('−', '-')));
  const w = parseFloat(d.w);
  return Math.max(1, Math.round(w * z * SCALE));
}

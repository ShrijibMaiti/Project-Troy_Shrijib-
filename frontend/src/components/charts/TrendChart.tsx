interface Props {
  values: number[];
  stroke: string;
}

/**
 * 90-day score trend, drawn to the fleet table's 180×28 cell.
 * Bespoke SVG rather than a Recharts LineChart: at 28px tall inside every
 * table row there are no axes, ticks or tooltips to gain, and one Recharts
 * instance per row is measurable overhead for zero visual difference. Same
 * reasoning (and documentation) as the Seismograph deviation — see
 * frontend/README.md.
 */
export default function TrendChart({ values, stroke }: Props) {
  const points = values
    .map((y, i) => `${(4 + i * 11.3).toFixed(1)},${(26 - (y / 80) * 24).toFixed(1)}`)
    .join(' ');
  return (
    <svg viewBox="0 0 200 28" className="block h-7 w-[180px]">
      <polyline points={points} fill="none" stroke={stroke} strokeWidth="1.5" />
    </svg>
  );
}

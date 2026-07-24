/**
 * DELIBERATE STACK DEVIATION — Seismograph is bespoke SVG, not Recharts,
 * because the clickable event markers must sit exactly on the polyline —
 * this is a deliberate deviation from strict §7 stack conformance
 * (Project-Troy.md), not an oversight. The markers are the product's hero
 * interaction surface (marker ↔ citation chip ↔ timeline sync), and their
 * position, hit area, and active state are pixel-exact here. Revisit if
 * pixel-perfect marker placement can be achieved inside a Recharts
 * ComposedChart with a custom dot renderer. See also frontend/README.md.
 */
interface Props {
  hist: number[];
  eventWeeks: { n: number; w: number }[];
  activeSignal: number;
  threshold: number;
  onMarkerClick: (n: number) => void;
}

const sy = (v: number) => 170 - (v / 90) * 160;
export default function Seismograph({ hist, eventWeeks, activeSignal, threshold, onMarkerClick }: Props) {
  const sx = (i: number) => 10 + i * (980 / (hist.length - 1));
  const points = hist.map((v, i) => `${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join(' ');
  const ty = sy(threshold);

  return (
    <svg viewBox="0 0 1000 190" className="block w-full">
      <line x1="0" y1={ty} x2="1000" y2={ty} stroke="#3A2226" strokeWidth="1" strokeDasharray="4 4" />
      <text x="994" y={ty - 5} textAnchor="end" fill="#E5484D" fontSize="9" fontFamily="Sometype Mono" opacity="0.7">
        {threshold}
      </text>
      <polyline points={points} fill="none" stroke="#B9B7B2" strokeWidth="1.5" />
      {eventWeeks.map((e) => {
        const active = activeSignal === e.n;
        const x = sx(e.w);
        const y = sy(hist[e.w]);
        return (
          <g key={e.n} className="cursor-pointer" onClick={() => onMarkerClick(e.n)}>
            <line
              x1={x}
              y1={y + 6}
              x2={x}
              y2="170"
              stroke={active ? '#E5484D' : '#26262B'}
              strokeWidth="1"
              strokeDasharray="2 3"
            />
            <circle
              cx={x}
              cy={y}
              r={active ? 6 : 4.5}
              fill={active ? '#E5484D' : '#0A0A0B'}
              stroke={active ? '#E5484D' : '#8A8A93'}
              strokeWidth="1.5"
            />
            <text x={x} y="184" textAnchor="middle" fill={active ? '#E5484D' : '#55555C'} fontSize="9" fontFamily="Sometype Mono">
              [{e.n}]
            </text>
          </g>
        );
      })}
    </svg>
  );
}

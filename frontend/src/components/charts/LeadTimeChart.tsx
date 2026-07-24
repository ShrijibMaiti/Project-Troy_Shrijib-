import {
  Bar,
  Cell,
  ComposedChart,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts';
import type { LeadBucket } from '@/types/api';

interface Props {
  buckets: LeadBucket[];
  medianDays: number;
  height?: number;
  medianLabel?: string;
}

/** Backtest lead-time distribution: equal-width buckets, median line interpolated within its bucket. */
export default function LeadTimeChart({ buckets, medianDays, height = 240, medianLabel }: Props) {
  const data = buckets.map((b, i) => ({ ...b, x: i + 1 }));
  const maxN = Math.max(...buckets.map((b) => b.n));
  const bounds = buckets.map((b) => b.label.split('–').map(Number) as [number, number]);
  const medianBucket = bounds.findIndex(([lo, hi]) => medianDays >= lo && medianDays < hi);
  const [mLo, mHi] = bounds[medianBucket];
  const medianX = medianBucket + 0.5 + (medianDays - mLo) / (mHi - mLo);
  const ticks = buckets.map((_, i) => i + 1);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 24, right: 8, bottom: 0, left: 8 }}>
        <XAxis
          type="number"
          dataKey="x"
          domain={[0.5, buckets.length + 0.5]}
          ticks={ticks}
          tickFormatter={(v: number) => buckets[v - 1]?.label ?? ''}
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#55555C', fontSize: 11, fontFamily: 'Sometype Mono' }}
        />
        <YAxis hide domain={[0, maxN * 1.1]} />
        <Bar dataKey="n" barSize={76} isAnimationActive={false}>
          {data.map((_, i) => (
            <Cell key={i} fill={i === medianBucket ? '#5FA57C' : '#26262B'} />
          ))}
          <LabelList
            dataKey="n"
            position="top"
            style={{ fill: '#B9B7B2', fontSize: 12, fontFamily: 'Sometype Mono' }}
          />
        </Bar>
        <ReferenceLine
          x={medianX}
          stroke="#5FA57C"
          strokeWidth={1}
          strokeDasharray="3 3"
          label={{
            value: medianLabel ?? `MEDIAN ${medianDays} DAYS`,
            position: 'insideTopLeft',
            fill: '#5FA57C',
            fontSize: 11,
            fontFamily: 'Sometype Mono',
            offset: 8,
          }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

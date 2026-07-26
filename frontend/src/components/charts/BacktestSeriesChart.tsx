import {
  CartesianGrid, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { SeriesPoint } from '@/types/api';

interface Props {
  series: SeriesPoint[];
  failedName: string;
  controlName: string;
  failureDate: string | null;
  height?: number;
}

/**
 * The real backtest curves. Plotted rather than summarised on purpose: the
 * reader should SEE that the control tracks the failure case and that the
 * failure signal spikes only at the event, not before it.
 */
export default function BacktestSeriesChart({
  series, failedName, controlName, failureDate, height = 260,
}: Props) {
  const font = { fontSize: 10, fontFamily: 'Sometype Mono' };
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={series} margin={{ top: 16, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="#26262B" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: '#55555C', ...font }}
          axisLine={false} tickLine={false}
          minTickGap={48}
          tickFormatter={(d: string) => d.slice(5)}
        />
        <YAxis
          domain={[0, 'dataMax + 0.5']}
          tick={{ fill: '#55555C', ...font }}
          axisLine={false} tickLine={false} width={34}
        />
        <Tooltip
          contentStyle={{ background: '#111114', border: '1px solid #26262B', ...font }}
          labelStyle={{ color: '#B9B7B2' }}
        />
        {failureDate && (
          <ReferenceLine
            x={failureDate}
            stroke="#9B3232"
            strokeDasharray="3 3"
            label={{ value: 'FAILURE', position: 'insideTopRight', fill: '#9B3232', ...font }}
          />
        )}
        <Line
          type="stepAfter" dataKey="failed" name={failedName}
          stroke="#9B3232" strokeWidth={2} dot={false} isAnimationActive={false}
          connectNulls
        />
        <Line
          type="stepAfter" dataKey="control" name={controlName}
          stroke="#B07D2B" strokeWidth={1.5} dot={false} isAnimationActive={false}
          strokeDasharray="4 3" connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
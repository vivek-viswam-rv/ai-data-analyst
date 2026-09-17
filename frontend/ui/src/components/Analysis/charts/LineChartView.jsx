import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatTick } from "utils/report";

const formatDateTick = (value) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

const LineChartView = ({ spec }) => (
  <ResponsiveContainer width="100%" height={280}>
    <LineChart data={spec.data}>
      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
      <XAxis
        dataKey={spec.x_key}
        tickFormatter={formatDateTick}
        tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
        label={{
          value: spec.x_label,
          position: "insideBottom",
          offset: -5,
          style: { fontSize: 12, fill: "var(--muted-foreground)" },
        }}
      />
      <YAxis
        tickFormatter={formatTick}
        tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
        label={{
          value: spec.y_label,
          angle: -90,
          position: "insideLeft",
          style: { fontSize: 12, fill: "var(--muted-foreground)" },
        }}
      />
      <Tooltip />
      {spec.series.length > 1 && <Legend />}
      {spec.series.map((s, i) => (
        <Line
          key={s}
          type="monotone"
          dataKey={s}
          stroke={`var(--chart-${(i % 5) + 1})`}
          strokeWidth={2}
          dot={false}
        />
      ))}
    </LineChart>
  </ResponsiveContainer>
);

export default LineChartView;

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatTick } from "utils/report";

const HistogramView = ({ spec }) => (
  <ResponsiveContainer width="100%" height={280}>
    <BarChart data={spec.data}>
      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
      <XAxis
        dataKey={spec.x_key}
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
      <Bar
        dataKey={spec.series[0]}
        fill="var(--chart-1)"
        radius={[4, 4, 0, 0]}
      />
    </BarChart>
  </ResponsiveContainer>
);

export default HistogramView;

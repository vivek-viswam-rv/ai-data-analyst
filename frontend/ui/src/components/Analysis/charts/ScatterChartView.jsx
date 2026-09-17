import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatTick } from "utils/report";

const ScatterChartView = ({ spec }) => (
  <ResponsiveContainer width="100%" height={320}>
    <ScatterChart data={spec.data}>
      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
      <XAxis
        dataKey="x"
        type="number"
        tickFormatter={formatTick}
        tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
        label={{
          value: spec.x_label,
          position: "insideBottom",
          offset: -5,
          style: { fontSize: 12, fill: "var(--muted-foreground)" },
        }}
      />
      <YAxis
        dataKey="y"
        type="number"
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
      <Scatter data={spec.data} fill="var(--chart-1)" />
    </ScatterChart>
  </ResponsiveContainer>
);

export default ScatterChartView;

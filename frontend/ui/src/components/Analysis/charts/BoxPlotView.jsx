import {
  Bar,
  CartesianGrid,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  useXAxisScale,
  useYAxisScale,
} from "recharts";

import { formatNumber, formatTick } from "utils/report";

// Box width matches the <=24px mark spec; whisker caps render narrower so the
// box itself stays the dominant shape.
const BOX_WIDTH = 24;
const WHISKER_CAP_WIDTH = 12;

const BoxPlotTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) {
    return null;
  }

  const row = payload[0].payload;

  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <p className="mb-1 font-medium">{row.group}</p>
      <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        <dt>n</dt>
        <dd className="text-right">{formatNumber(row.n)}</dd>
        <dt>Max</dt>
        <dd className="text-right">{formatTick(row.max)}</dd>
        <dt>Q3</dt>
        <dd className="text-right">{formatTick(row.q3)}</dd>
        <dt>Median</dt>
        <dd className="text-right">{formatTick(row.median)}</dd>
        <dt>Q1</dt>
        <dd className="text-right">{formatTick(row.q1)}</dd>
        <dt>Min</dt>
        <dd className="text-right">{formatTick(row.min)}</dd>
        <dt>Outliers</dt>
        <dd className="text-right">{row.outliers ?? 0}</dd>
      </dl>
    </div>
  );
};

// Draws the whiskers (min-to-q1 and q3-to-max, never crossing the box, so
// z-order relative to the Bar never matters) plus the median line, which is
// drawn in the surface color so it reads on top of the box fill. Rendered as
// a plain child of ComposedChart: Recharts 3 renders arbitrary elements
// anywhere in the tree and these hooks read the chart's own scales.
const BoxPlotWhiskers = ({ data, xKey }) => {
  const xScale = useXAxisScale();
  const yScale = useYAxisScale();

  if (!xScale || !yScale) {
    return null;
  }

  return (
    <g>
      {data.map((row) => {
        const cx = xScale(row[xKey], { position: "middle" });
        if (cx == null) {
          return null;
        }

        const yMin = yScale(row.min);
        const yQ1 = yScale(row.q1);
        const yQ3 = yScale(row.q3);
        const yMax = yScale(row.max);
        const yMedian = yScale(row.median);

        return (
          <g key={row[xKey]}>
            <line
              x1={cx}
              x2={cx}
              y1={yMin}
              y2={yQ1}
              stroke="var(--muted-foreground)"
              strokeWidth={1.5}
            />
            <line
              x1={cx}
              x2={cx}
              y1={yQ3}
              y2={yMax}
              stroke="var(--muted-foreground)"
              strokeWidth={1.5}
            />
            <line
              x1={cx - WHISKER_CAP_WIDTH / 2}
              x2={cx + WHISKER_CAP_WIDTH / 2}
              y1={yMin}
              y2={yMin}
              stroke="var(--muted-foreground)"
              strokeWidth={1.5}
            />
            <line
              x1={cx - WHISKER_CAP_WIDTH / 2}
              x2={cx + WHISKER_CAP_WIDTH / 2}
              y1={yMax}
              y2={yMax}
              stroke="var(--muted-foreground)"
              strokeWidth={1.5}
            />
            <line
              x1={cx - BOX_WIDTH / 2}
              x2={cx + BOX_WIDTH / 2}
              y1={yMedian}
              y2={yMedian}
              stroke="var(--background)"
              strokeWidth={2}
              strokeLinecap="round"
            />
          </g>
        );
      })}
    </g>
  );
};

const BoxPlotView = ({ spec }) => {
  const extremes = spec.data.flatMap((row) => [row.min, row.max]);
  const dataMin = Math.min(...extremes);
  const dataMax = Math.max(...extremes);
  const padding = (dataMax - dataMin) * 0.1 || Math.abs(dataMax) * 0.1 || 1;
  const domain = [dataMin - padding, dataMax + padding];

  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart
        data={spec.data}
        margin={{ top: 8, right: 8, left: 0, bottom: 8 }}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="var(--border)"
          vertical={false}
        />
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
          domain={domain}
          tickFormatter={formatTick}
          tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
          label={{
            value: spec.y_label,
            angle: -90,
            position: "insideLeft",
            style: { fontSize: 12, fill: "var(--muted-foreground)" },
          }}
        />
        <Tooltip
          content={<BoxPlotTooltip />}
          cursor={{ fill: "var(--muted)", opacity: 0.3 }}
        />
        <Bar
          dataKey={(row) => [row.q1, row.q3]}
          barSize={BOX_WIDTH}
          fill="var(--chart-1)"
          radius={3}
          isAnimationActive={false}
        />
        <BoxPlotWhiskers data={spec.data} xKey={spec.x_key} />
      </ComposedChart>
    </ResponsiveContainer>
  );
};

export default BoxPlotView;

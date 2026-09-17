import ChartCard from "components/Analysis/charts/ChartCard";

const Charts = ({ report }) => (
  <div className="space-y-4">
    <p className="text-sm text-muted-foreground">{report.summary}</p>
    <div className="grid gap-4 sm:grid-cols-2">
      {report.charts.map((chart) => (
        <div
          key={chart.id}
          className={
            chart.type === "line" || chart.type === "box"
              ? "sm:col-span-2"
              : undefined
          }
        >
          <ChartCard spec={chart} />
        </div>
      ))}
    </div>
  </div>
);

export default Charts;

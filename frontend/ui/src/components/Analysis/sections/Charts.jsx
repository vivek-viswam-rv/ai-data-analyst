import ChartCard from "components/Analysis/charts/ChartCard";

const Charts = ({ report }) => (
  <div className="space-y-4">
    <p className="text-sm text-muted-foreground">{report.summary}</p>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {report.charts.map((chart) => (
        <ChartCard key={chart.id} spec={chart} />
      ))}
    </div>
  </div>
);

export default Charts;

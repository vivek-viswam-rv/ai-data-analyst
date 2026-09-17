import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "shadcn/card";

import BarChartView from "./BarChartView";
import HistogramView from "./HistogramView";
import LineChartView from "./LineChartView";
import ScatterChartView from "./ScatterChartView";

const CHART_VIEWS = {
  bar: BarChartView,
  line: LineChartView,
  scatter: ScatterChartView,
  histogram: HistogramView,
};

const ChartCard = ({ spec }) => {
  const ChartView = CHART_VIEWS[spec.type];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{spec.title}</CardTitle>
        <CardDescription>{spec.caption}</CardDescription>
      </CardHeader>
      <CardContent>{ChartView && <ChartView spec={spec} />}</CardContent>
    </Card>
  );
};

export default ChartCard;

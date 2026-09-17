import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "shadcn/card";

import BarChartView from "./BarChartView";
import BoxPlotView from "./BoxPlotView";
import HistogramView from "./HistogramView";
import LineChartView from "./LineChartView";
import ScatterChartView from "./ScatterChartView";

const CHART_VIEWS = {
  bar: BarChartView,
  line: LineChartView,
  scatter: ScatterChartView,
  histogram: HistogramView,
  box: BoxPlotView,
};

const ChartCard = ({ spec }) => {
  const ChartView = CHART_VIEWS[spec.type];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{spec.title}</CardTitle>
      </CardHeader>
      <CardContent>
        {ChartView ? (
          <ChartView spec={spec} />
        ) : (
          <p className="text-sm text-muted-foreground">Unsupported chart</p>
        )}
      </CardContent>
      <CardFooter>
        <p className="text-sm text-muted-foreground">{spec.caption}</p>
      </CardFooter>
    </Card>
  );
};

export default ChartCard;

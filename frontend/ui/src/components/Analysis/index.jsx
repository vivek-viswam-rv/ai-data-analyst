import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";

import ThemeToggle from "components/commons/ThemeToggle";
import { HOME_ROUTE } from "components/routeConstants";
import { AGENT_LABELS } from "constants/analysis";
import useAnalysisStream from "hooks/useAnalysisStream";
import { Alert, AlertDescription, AlertTitle } from "shadcn/alert";
import { Button } from "shadcn/button";
import { Card, CardContent } from "shadcn/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "shadcn/empty";
import { Skeleton } from "shadcn/skeleton";

import AgentRail from "./AgentRail";
import DownloadButtons from "./DownloadButtons";
import Anomalies from "./sections/Anomalies";
import Charts from "./sections/Charts";
import DataQuality from "./sections/DataQuality";
import Exploration from "./sections/Exploration";
import Statistics from "./sections/Statistics";
import Summary from "./sections/Summary";

// interpretation is rendered separately (pinned above this list), so it is
// deliberately left out here.
const REMAINING_AGENT_ORDER = [
  "data_quality",
  "eda",
  "statistics",
  "anomaly",
  "visualization",
];

const SECTION_COMPONENTS = {
  data_quality: DataQuality,
  eda: Exploration,
  statistics: Statistics,
  anomaly: Anomalies,
  visualization: Charts,
};

// Rough shape of each section, so the loading state hints at what is coming
// (a table-heavy report gets more bars, the chart section gets a big block).
const SECTION_PLACEHOLDER_SHAPES = {
  data_quality: { bars: 4 },
  eda: { bars: 3 },
  statistics: { bars: 4 },
  anomaly: { bars: 3 },
  visualization: { bars: 1, chart: true },
};

const SectionPlaceholder = ({ bars = 3, chart = false }) => (
  <Card>
    <CardContent className="space-y-3">
      <Skeleton className="h-5 w-40" />
      {chart && <Skeleton className="h-40 w-full" />}
      {Array.from({ length: bars }).map((_, index) => (
        <Skeleton
          key={index}
          className="h-4"
          style={{ width: `${85 - index * 18}%` }}
        />
      ))}
    </CardContent>
  </Card>
);

const Analysis = () => {
  const location = useLocation();
  const { state, start, hydrate } = useAnalysisStream();
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (hasInitialized.current) {
      return;
    }
    hasInitialized.current = true;

    if (location.state?.file) {
      start(location.state.file, location.state.goal);
    } else {
      hydrate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (state.status === "idle") {
    return (
      <div className="flex min-h-svh items-center justify-center bg-background px-4 text-foreground">
        <Empty>
          <EmptyHeader>
            <EmptyTitle>No analysis to show</EmptyTitle>
            <EmptyDescription>Upload a file to get started</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button asChild>
              <Link to={HOME_ROUTE}>Go to upload</Link>
            </Button>
          </EmptyContent>
        </Empty>
      </div>
    );
  }

  return (
    <div className="min-h-svh bg-background px-4 py-8 text-foreground">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex items-center justify-between gap-4 border-b pb-4">
          <div>
            <Link
              to={HOME_ROUTE}
              className="text-sm font-semibold hover:underline"
            >
              AI Data Analyst
            </Link>
            {state.restored && (
              <p className="text-xs text-muted-foreground">
                Showing your last completed analysis
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <DownloadButtons state={state} />
            <ThemeToggle />
          </div>
        </div>

        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          <div className="lg:w-64 lg:shrink-0">
            <AgentRail
              agents={state.agents}
              agentStatus={state.agentStatus}
              elapsedMs={state.elapsedMs}
              status={state.status}
            />
          </div>

          <div className="min-w-0 flex-1 space-y-6">
            {state.runError && (
              <Alert variant="destructive">
                <AlertTitle>Analysis failed</AlertTitle>
                <AlertDescription>{state.runError}</AlertDescription>
              </Alert>
            )}

            {state.reports.interpretation && (
              <Summary report={state.reports.interpretation} />
            )}

            {REMAINING_AGENT_ORDER.map((agentId) => {
              if (state.agentStatus[agentId] === "failed") {
                return (
                  <Alert key={agentId} variant="destructive">
                    <AlertTitle>{AGENT_LABELS[agentId]} failed</AlertTitle>
                    <AlertDescription>
                      {state.agentMessages[agentId]}
                    </AlertDescription>
                  </Alert>
                );
              }

              if (state.reports[agentId]) {
                const SectionComponent = SECTION_COMPONENTS[agentId];
                return (
                  <SectionComponent
                    key={agentId}
                    report={state.reports[agentId]}
                  />
                );
              }

              return (
                <SectionPlaceholder
                  key={agentId}
                  {...SECTION_PLACEHOLDER_SHAPES[agentId]}
                />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analysis;

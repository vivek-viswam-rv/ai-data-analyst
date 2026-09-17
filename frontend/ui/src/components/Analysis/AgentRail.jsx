import { Circle, CircleCheck, CircleX, Loader2 } from "lucide-react";

import { AGENT_LABELS } from "constants/analysis";
import { Card } from "shadcn/card";

const STATUS_ICONS = {
  waiting: <Circle className="size-4 text-muted-foreground" />,
  running: <Loader2 className="size-4 animate-spin text-foreground" />,
  done: (
    <CircleCheck className="size-4 text-emerald-600 dark:text-emerald-400" />
  ),
  failed: <CircleX className="size-4 text-destructive" />,
};

const formatElapsed = (elapsedMs) => {
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
};

const AgentRail = ({ agents, agentStatus, elapsedMs, status }) => {
  const showTimer = status === "running" || status === "done";
  const timerLabel = status === "running" ? "Elapsed" : "Completed in";

  return (
    <Card className="gap-4 py-4">
      <nav aria-label="Analysis progress" className="space-y-1 px-4">
        {agents.map((agentId) => (
          <div
            key={agentId}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm"
          >
            {STATUS_ICONS[agentStatus[agentId]] ?? STATUS_ICONS.waiting}
            <span
              className={
                agentStatus[agentId] === "waiting"
                  ? "text-muted-foreground"
                  : "text-foreground"
              }
            >
              {AGENT_LABELS[agentId] ?? agentId}
            </span>
          </div>
        ))}
      </nav>

      {showTimer && (
        <div className="border-t px-4 pt-3 text-xs text-muted-foreground">
          {timerLabel}:{" "}
          <span className="font-medium text-foreground">
            {formatElapsed(elapsedMs)}
          </span>
        </div>
      )}
    </Card>
  );
};

export default AgentRail;

import { FileText, RotateCcw } from "lucide-react";

import { Button } from "shadcn/button";

const formatBytes = (bytes) => `${(bytes / 1_000_000).toFixed(1)} MB`;

const ActionBar = ({ file, canAnalyze, onAnalyze, onReset }) => (
  <div className="flex flex-wrap items-center justify-between gap-3">
    <div className="flex min-w-0 items-center gap-2 rounded-md border bg-accent/40 px-3 py-1.5">
      <FileText className="size-4 text-muted-foreground" />
      <span className="truncate text-sm font-medium">{file.name}</span>
      <span className="text-xs text-muted-foreground">
        {formatBytes(file.size)}
      </span>
    </div>
    <div className="flex items-center gap-2">
      <Button type="button" variant="outline" onClick={onReset}>
        <RotateCcw className="size-4" />
        Start over
      </Button>
      <Button type="button" disabled={!canAnalyze} onClick={onAnalyze}>
        Analyze
      </Button>
    </div>
  </div>
);

export default ActionBar;

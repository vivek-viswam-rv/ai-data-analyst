import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { FlaskConical, Loader2 } from "lucide-react";

import GithubLink from "components/commons/GithubLink";
import ThemeToggle from "components/commons/ThemeToggle";
import { ANALYSIS_ROUTE } from "components/routeConstants";
import {
  ACCEPTED_FILE_EXTENSIONS,
  DEFAULT_MAX_UPLOAD_BYTES,
  EXAMPLE_DATASET,
  GOAL_MAX_LENGTH,
} from "constants/analysis";
import { useFetchLimits, usePreview } from "hooks/reactQuery/useAnalysesApi";
import { Button } from "shadcn/button";
import { Skeleton } from "shadcn/skeleton";
import { Textarea } from "shadcn/textarea";

import BriefPreview from "./BriefPreview";
import DropZone from "./DropZone";

const formatBytes = (bytes) => `${(bytes / 1_000_000).toFixed(1)} MB`;

const Upload = () => {
  const navigate = useNavigate();
  const limits = useFetchLimits();
  const previewMutation = usePreview();

  const [file, setFile] = useState(null);
  const [goal, setGoal] = useState("");
  const [isLoadingExample, setIsLoadingExample] = useState(false);

  const effectiveMaxBytes =
    limits?.data?.max_upload_bytes ?? DEFAULT_MAX_UPLOAD_BYTES;

  const onFileSelected = (selectedFile) => {
    const extension = selectedFile.name
      .slice(selectedFile.name.lastIndexOf("."))
      .toLowerCase();

    if (!ACCEPTED_FILE_EXTENSIONS.includes(extension)) {
      toast.error("Unsupported file type. Use CSV, TSV, TXT, XLS or XLSX.");
      return;
    }

    if (selectedFile.size > effectiveMaxBytes) {
      toast.error(`File exceeds the ${formatBytes(effectiveMaxBytes)} limit.`);
      return;
    }

    previewMutation.reset();
    setFile(selectedFile);
    previewMutation.mutate(selectedFile);
  };

  const onTryExample = async () => {
    setIsLoadingExample(true);

    try {
      const response = await fetch(EXAMPLE_DATASET.url);

      if (!response.ok) {
        throw new Error("Failed to fetch example dataset");
      }

      const blob = await response.blob();
      const exampleFile = new File([blob], EXAMPLE_DATASET.filename, {
        type: "text/csv",
      });

      if (!goal.trim()) {
        setGoal(EXAMPLE_DATASET.goal);
      }

      onFileSelected(exampleFile);
    } catch {
      toast.error("Could not load the example dataset.");
    } finally {
      setIsLoadingExample(false);
    }
  };

  return (
    <div className="min-h-svh bg-background px-4 py-8 text-foreground">
      <div className="mx-auto max-w-4xl space-y-8">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold">AI Data Analyst</h1>
            <p className="text-sm text-muted-foreground">
              Upload a CSV or Excel file and a team of agents will analyze it.
            </p>
          </div>
          <div className="flex items-center gap-1">
            <GithubLink />
            <ThemeToggle />
          </div>
        </div>

        <div className="space-y-4">
          <div className="space-y-1">
            <Button
              type="button"
              variant="secondary"
              size="lg"
              className="h-14 w-full text-base"
              disabled={isLoadingExample || previewMutation.isPending}
              onClick={onTryExample}
            >
              {isLoadingExample ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <FlaskConical className="size-5" />
              )}
              Try the example dataset
            </Button>
            <p className="text-xs text-muted-foreground">
              606 rows of synthetic sales data with a few planted problems to
              find.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs text-muted-foreground">or</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <DropZone
            maxBytes={effectiveMaxBytes}
            filename={file?.name}
            onFileSelected={onFileSelected}
          />

          {previewMutation.isPending && (
            <div className="space-y-3">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-32" />
              <div className="space-y-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            </div>
          )}

          {previewMutation.isSuccess && (
            <BriefPreview brief={previewMutation.data.brief} />
          )}
        </div>

        <div className="space-y-2">
          <label htmlFor="goal" className="text-sm font-medium">
            What do you want to know? (optional)
          </label>
          <Textarea
            id="goal"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            maxLength={GOAL_MAX_LENGTH}
            placeholder="e.g. Are there any unusual trends in monthly revenue?"
          />
          <p className="text-right text-xs text-muted-foreground">
            {goal.length}/{GOAL_MAX_LENGTH}
          </p>
        </div>

        <div className="flex justify-end">
          <Button
            disabled={!previewMutation.isSuccess || !file}
            onClick={() =>
              navigate(ANALYSIS_ROUTE, {
                state: { file, goal: goal.trim() || null },
              })
            }
          >
            Analyze
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Upload;

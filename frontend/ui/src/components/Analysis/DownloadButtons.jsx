import { FileJson, FileText } from "lucide-react";

import { Button } from "shadcn/button";
import { buildMarkdownReport } from "utils/report";

const downloadBlob = (content, type, filename) => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

const DownloadButtons = ({ state }) => {
  const disabled = Object.keys(state.reports).length === 0;

  const downloadMarkdown = () => {
    const markdown = buildMarkdownReport(state);
    downloadBlob(markdown, "text/markdown", "analysis.md");
  };

  const downloadJson = () => {
    const json = JSON.stringify(
      { reports: state.reports, errors: state.runErrors },
      null,
      2
    );
    downloadBlob(json, "application/json", "analysis.json");
  };

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={downloadMarkdown}
      >
        <FileText className="size-4" />
        Markdown
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={downloadJson}
      >
        <FileJson className="size-4" />
        JSON
      </Button>
    </div>
  );
};

export default DownloadButtons;

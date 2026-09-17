import { useRef, useState } from "react";
import { FileText, UploadCloud } from "lucide-react";

import { ACCEPTED_FILE_EXTENSIONS } from "constants/analysis";

const formatBytes = (bytes) => `${(bytes / 1_000_000).toFixed(1)} MB`;

const DropZone = ({ maxBytes, filename, onFileSelected }) => {
  const inputRef = useRef(null);
  const [isDragActive, setIsDragActive] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = () => {
    setIsDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragActive(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      onFileSelected(droppedFile);
    }
  };

  const handleChange = (e) => {
    const selected = e.target.files?.[0];
    if (selected) {
      onFileSelected(selected);
    }
    e.target.value = "";
  };

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
        isDragActive
          ? "border-primary bg-accent/50"
          : "border-border hover:border-primary/50 hover:bg-accent/30"
      }`}
    >
      <input
        type="file"
        accept={ACCEPTED_FILE_EXTENSIONS.join(",")}
        className="hidden"
        ref={inputRef}
        onChange={handleChange}
      />
      <UploadCloud className="size-8 text-muted-foreground" />
      <p className="text-sm font-medium">Click to upload or drag and drop</p>
      <p className="text-xs text-muted-foreground">
        {ACCEPTED_FILE_EXTENSIONS.join(", ").toUpperCase()} · Up to{" "}
        {formatBytes(maxBytes)}
      </p>
      {filename && (
        <div className="mt-3 flex items-center gap-2 rounded-md border bg-accent/40 px-3 py-1.5">
          <FileText className="size-4 text-muted-foreground" />
          <span className="text-sm font-medium">{filename}</span>
        </div>
      )}
    </div>
  );
};

export default DropZone;

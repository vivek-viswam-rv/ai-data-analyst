// The agents, in the order the backend runs them (see
// backend/app/analysis/state.py AGENT_ORDER). Kept as a constant so the rail
// can render immediately, before the `brief` event confirms the same list.
export const AGENT_ORDER = [
  "data_quality",
  "eda",
  "visualization",
  "interpretation",
];

export const AGENT_LABELS = {
  data_quality: "Data quality",
  eda: "Exploration",
  visualization: "Charts",
  interpretation: "Summary",
};

// Maps an agent id to the key its report is filed under in the `done` event's
// `reports` object (see backend/app/analysis/state.py REPORT_KEYS).
export const AGENT_REPORT_KEY = {
  data_quality: "quality",
  eda: "eda",
  visualization: "charts",
  interpretation: "interpretation",
};

export const DEFAULT_MAX_UPLOAD_BYTES = 4_500_000;

export const ACCEPTED_FILE_EXTENSIONS = [
  ".csv",
  ".tsv",
  ".txt",
  ".xlsx",
  ".xls",
];

export const GOAL_MAX_LENGTH = 500;

export const ANALYSIS_STORAGE_KEY = "ai-data-analyst:last-run";

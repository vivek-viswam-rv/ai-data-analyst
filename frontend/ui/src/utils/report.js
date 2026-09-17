import { AGENT_LABELS } from "constants/analysis";

import { isPresent } from "utils";

// Rounds `value` to `sigFigs` significant figures and returns it as a plain
// string (no trailing-zero padding, no scientific notation for the ranges
// this app deals with).
export const formatSignificant = (value, sigFigs = 3) => {
  if (!isPresent(value) || Number.isNaN(value)) {
    return "—";
  }
  if (value === 0) {
    return "0";
  }
  const digits = sigFigs - Math.ceil(Math.log10(Math.abs(value)));
  const factor = 10 ** digits;
  const rounded = Math.round(value * factor) / factor;
  return String(Object.is(rounded, -0) ? 0 : rounded);
};

// p-values: 3 significant figures, but anything smaller than 0.001 reads as
// "<0.001" rather than a string of leading zeros.
export const formatPValue = (value) => {
  if (!isPresent(value) || Number.isNaN(value)) {
    return "—";
  }
  if (value < 0.001) {
    return "<0.001";
  }
  return formatSignificant(value, 3);
};

export const formatPercent = (value, digits = 1) =>
  isPresent(value) ? `${Number(value).toFixed(digits)}%` : "—";

// Compact number formatting for chart axis ticks (1200 -> "1.2K").
export const formatTick = (value) => {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return value;
  }
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
};

export const formatNumber = (value) =>
  isPresent(value) ? new Intl.NumberFormat("en-US").format(value) : "—";

// Escapes a free-text value for safe interpolation into a markdown table
// cell: pipes would otherwise split the cell, newlines would break the row.
const escapeMarkdownCell = (text) =>
  String(text ?? "")
    .replace(/\|/g, "\\|")
    .replace(/\r?\n/g, " ");

const buildMarkdownTable = (headers, rows) => {
  const headerRow = `| ${headers.join(" | ")} |`;
  const separatorRow = `| ${headers.map(() => "---").join(" | ")} |`;
  const bodyRows = rows.map((row) => `| ${row.join(" | ")} |`);
  return [headerRow, separatorRow, ...bodyRows].join("\n");
};

const buildBulletList = (items) => items.map((item) => `- ${item}`).join("\n");

const buildInterpretationSections = (interpretation) => [
  "## Executive summary",
  interpretation.executive_summary,
  "## Key insights",
  buildBulletList(interpretation.key_insights),
  "## Recommendations",
  buildMarkdownTable(
    ["Priority", "Title", "Detail"],
    interpretation.recommendations.map((recommendation) => [
      escapeMarkdownCell(recommendation.priority),
      escapeMarkdownCell(recommendation.title),
      escapeMarkdownCell(recommendation.detail),
    ])
  ),
  "## Open questions",
  buildBulletList(interpretation.open_questions),
  "## Limitations",
  buildBulletList(interpretation.limitations),
];

const buildDataQualitySections = (report) => [
  `Score: ${report.score}`,
  report.summary,
  buildMarkdownTable(
    [
      "Severity",
      "Column",
      "Kind",
      "Affected rows",
      "Description",
      "Suggestion",
    ],
    report.issues.map((issue) => [
      escapeMarkdownCell(issue.severity),
      escapeMarkdownCell(issue.column ?? "—"),
      escapeMarkdownCell(issue.kind),
      escapeMarkdownCell(issue.affected_rows ?? "—"),
      escapeMarkdownCell(issue.description),
      escapeMarkdownCell(issue.suggestion),
    ])
  ),
  buildBulletList(report.cleaning_steps),
];

const buildEdaSections = (report) => [
  report.summary,
  buildBulletList(
    report.distributions.map(
      (distribution) =>
        `**${distribution.column}** (${distribution.shape.replace(/_/g, " ")}): ${distribution.detail}`
    )
  ),
  buildBulletList(
    report.findings.map(
      (finding) =>
        `**${finding.title}**: ${finding.detail} (${finding.columns.join(", ")})`
    )
  ),
];

const buildVisualizationSections = (report) => [
  report.summary,
  buildBulletList(
    report.charts.map((chart) => `**${chart.title}** — ${chart.caption}`)
  ),
];

const AGENT_REPORT_SECTION_BUILDERS = {
  data_quality: buildDataQualitySections,
  eda: buildEdaSections,
  visualization: buildVisualizationSections,
};

export const buildMarkdownReport = (state) => {
  const sections = [`# Analysis: ${state.filename ?? "Untitled"}`];

  if (state.goal) {
    sections.push(`> ${state.goal}`);
  }

  const interpretation = state.reports.interpretation;
  if (interpretation) {
    sections.push(...buildInterpretationSections(interpretation));
  }

  Object.keys(AGENT_REPORT_SECTION_BUILDERS).forEach((agentId) => {
    const failureMessage = state.agentMessages[agentId];
    const report = state.reports[agentId];

    if (!failureMessage && !report) {
      return;
    }

    sections.push(`## ${AGENT_LABELS[agentId]}`);

    if (failureMessage) {
      sections.push(`_Failed: ${failureMessage}_`);
      return;
    }

    sections.push(...AGENT_REPORT_SECTION_BUILDERS[agentId](report));
  });

  return sections.join("\n\n");
};

"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";
import { DiffEditor, type Monaco } from "@monaco-editor/react";
import Link from "next/link";
import { ChevronDown, ChevronUp, Link as LinkIcon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import type { PluggableList } from "unified";
import { CartesianGrid, Customized, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

import { parseOutputString } from "@/lib/utils";
import { ChartContainer } from "@/components/ui/chart";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ReportBlock, { ReportBlockProps, type BlockComponent } from "./ReportBlock";
import { Gauge } from "@/components/gauge";
import { ac1GaugeSegments } from "@/components/ui/scorecard-evaluation";
import { GaugeThresholdComputer } from "@/utils/gauge-thresholds";
import {
  applyMonacoTheme,
  configureYamlLanguage,
  defineCustomMonacoThemes,
  getCommonMonacoOptions,
  setupMonacoThemeWatcher,
} from "@/lib/monaco-theme";

const markdownPlugins: PluggableList = [remarkGfm, remarkBreaks];

interface MetricPayload {
  alignment?: number | null;
  accuracy?: number | null;
  precision?: number | null;
  recall?: number | null;
  cost?: number | null;
  evaluation_id?: string | null;
  created_at?: string | null;
  processed_items?: number | null;
  total_items?: number | null;
}

interface ChampionPoint {
  point_index: number;
  label: string;
  entered_at: string;
  exited_at?: string | null;
  version_id: string;
  version_note?: string | null;
  version_branch?: string | null;
  previous_champion_version_id?: string | null;
  next_champion_version_id?: string | null;
  transition_id?: string | null;
  feedback_evaluation_id?: string | null;
  feedback_metrics?: MetricPayload | null;
  regression_evaluation_id?: string | null;
  regression_metrics?: MetricPayload | null;
}

interface VersionDiff {
  left_version_id?: string | null;
  left_version_note?: string | null;
  left_version_created_at?: string | null;
  right_version_id?: string | null;
  right_version_note?: string | null;
  right_version_created_at?: string | null;
  configuration_left?: string | null;
  configuration_right?: string | null;
  configuration_diff?: string | null;
  guidelines_left?: string | null;
  guidelines_right?: string | null;
  guidelines_diff?: string | null;
  message?: string | null;
}

interface CostPayload {
  overall?: number | null;
  inference?: number | null;
  evaluation?: number | null;
}

interface OptimizationSummary {
  procedure_count?: number;
  evaluation_count?: number;
  score_result_count?: number;
  optimization_cost?: CostPayload | null;
  associated_evaluation_cost?: number | null;
}

interface SmeInformation {
  procedure_id?: string | null;
  procedure_status?: string | null;
  procedure_created_at?: string | null;
  procedure_updated_at?: string | null;
  available?: boolean;
  agenda?: string | null;
  agenda_gated?: string | null;
  agenda_raw?: string | null;
  worksheet?: string | null;
  run_summary?: Record<string, unknown> | null;
  generated_at?: string | null;
}

interface MetricChange {
  before?: number | null;
  after?: number | null;
  delta?: number | null;
}

interface DatasetPerformanceSummary {
  before_evaluation_id?: string | null;
  after_evaluation_id?: string | null;
  alignment?: MetricChange | null;
  accuracy?: MetricChange | null;
}

interface PerformanceSummary {
  before_version_id?: string | null;
  after_version_id?: string | null;
  feedback?: DatasetPerformanceSummary | null;
  regression?: DatasetPerformanceSummary | null;
}

interface ChampionScoreSeries {
  score_id: string;
  score_name: string;
  optimization_summary?: OptimizationSummary | null;
  performance_summary?: PerformanceSummary | null;
  sme?: SmeInformation | null;
  points: ChampionPoint[];
  champion_change_count?: number;
  new_champion_count?: number;
  diff?: VersionDiff | null;
}

interface ScoreChampionVersionTimelineData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
  scope?: "single_score" | "all_scores";
  scorecard_id?: string;
  scorecard_name?: string;
  date_range?: {
    start: string;
    end: string;
    normalized_to_activity?: boolean;
  };
  requested_date_range?: {
    start: string;
    end: string;
  };
  scores?: ChampionScoreSeries[];
  summary?: {
    scores_analyzed?: number;
    scores_with_champion_changes?: number;
    scores_with_new_champions?: number;
    champion_change_count?: number;
    new_champion_count?: number;
    procedure_count?: number;
    evaluation_count?: number;
    score_result_count?: number;
    optimization_cost?: CostPayload | null;
    associated_evaluation_cost?: number | null;
    score_versions_scanned?: number;
    evaluations_scanned?: number;
    procedure_records_scanned?: number;
  };
  message?: string;
  warning?: string;
  error?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

const chartConfig = {
  feedback_alignment: { label: "Feedback AC1", color: "var(--chart-1)" },
  regression_alignment: { label: "Regression AC1", color: "var(--chart-2)" },
  feedback_accuracy: { label: "Feedback Accuracy", color: "var(--chart-1)" },
  regression_accuracy: { label: "Regression Accuracy", color: "var(--chart-2)" },
};

const accuracyGaugeSegments = GaugeThresholdComputer.createSegments(
  GaugeThresholdComputer.computeThresholds({})
);

const metricKeys = [
  "feedback_alignment",
  "regression_alignment",
  "feedback_accuracy",
  "regression_accuracy",
] as const;

type MetricKey = (typeof metricKeys)[number];

const chartMargin = { top: 8, right: 52, left: 20, bottom: 40 };

type ChartPoint = ChampionPoint & {
  entered_at_timestamp: number;
  feedback_alignment: number | null;
  regression_alignment: number | null;
  feedback_accuracy: number | null;
  regression_accuracy: number | null;
};

const formatNumber = (value: number | null | undefined, decimals = 3): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return value.toFixed(decimals);
};

const formatAccuracy = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return value <= 1 ? `${(value * 100).toFixed(1)}%` : `${value.toFixed(1)}%`;
};

const formatSignedNumber = (value: number | null | undefined, decimals = 3): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}`;
};

const formatSignedAccuracyDelta = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  const normalized = value <= 1 && value >= -1 ? value * 100 : value;
  const sign = normalized > 0 ? "+" : "";
  return `${sign}${normalized.toFixed(1)} pts`;
};

const formatInteger = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "0";
  return Math.round(value).toLocaleString();
};

const formatCurrency = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
};

const formatDateTime = (value?: string | null): string => {
  if (!value) return "N/A";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

const formatAxisDate = (value: number): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

const shortId = (value?: string | null): string => {
  if (!value) return "N/A";
  return value.length > 12 ? value.slice(0, 8) : value;
};

const scoreHref = (scorecardId?: string | null, scoreId?: string | null): string | null => {
  if (!scorecardId || !scoreId) return null;
  return `/lab/scorecards/${encodeURIComponent(scorecardId)}/scores/${encodeURIComponent(scoreId)}`;
};

const scoreVersionHref = (
  scorecardId?: string | null,
  scoreId?: string | null,
  scoreVersionId?: string | null
): string | null => {
  if (!scorecardId || !scoreId || !scoreVersionId) return null;
  return `${scoreHref(scorecardId, scoreId)}/versions/${encodeURIComponent(scoreVersionId)}`;
};

const RecordLink: React.FC<{
  href?: string | null;
  label: string;
  size?: "sm" | "md";
}> = ({ href, label, size = "sm" }) => {
  if (!href) return null;

  return (
    <Link
      href={href}
      aria-label={label}
      title={label}
      className="shrink-0 rounded-sm text-foreground transition-colors hover:bg-card"
      onClick={(event) => event.stopPropagation()}
    >
      <LinkIcon className={size === "md" ? "h-4 w-4" : "h-3.5 w-3.5"} />
    </Link>
  );
};

const LinkedShortId: React.FC<{
  id?: string | null;
  href?: string | null;
  label: string;
  className?: string;
  iconSize?: "sm" | "md";
}> = ({ id, href, label, className = "", iconSize = "sm" }) => (
  <span className={`inline-flex min-w-0 items-center gap-1.5 ${className}`}>
    <span className="truncate font-mono">{shortId(id)}</span>
    {id ? <RecordLink href={href} label={label} size={iconSize} /> : null}
  </span>
);

const ExpandCaretControl: React.FC<{
  isExpanded: boolean;
  onClick: () => void;
  expandLabel: string;
  collapseLabel: string;
}> = ({ isExpanded, onClick, expandLabel, collapseLabel }) => (
  <div className="flex flex-col items-center">
    <div className="mb-1 h-px w-full bg-border" />
    <button
      type="button"
      onClick={onClick}
      className="flex items-center justify-center rounded-full p-0.5 transition-colors hover:bg-muted/50"
      aria-label={isExpanded ? collapseLabel : expandLabel}
      aria-expanded={isExpanded}
    >
      {isExpanded ? (
        <ChevronUp className="h-3 w-3 text-muted-foreground" />
      ) : (
        <ChevronDown className="h-3 w-3 text-muted-foreground" />
      )}
    </button>
  </div>
);

const chartAccuracy = (value: number | null | undefined): number | null => {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return value <= 1 ? value * 100 : value;
};

const CircleDot = (props: any) => {
  const { cx, cy, fill } = props;
  if (cx == null || cy == null) return null;
  return <circle cx={cx} cy={cy} r={4} fill={fill} stroke="none" />;
};

const SquareDot = (props: any) => {
  const { cx, cy, fill } = props;
  if (cx == null || cy == null) return null;
  return <rect x={cx - 4} y={cy - 4} width={8} height={8} fill={fill} stroke="none" />;
};

const LeftAxisTick: React.FC<any> = ({ x = 0, y = 0, payload }) => {
  const value = payload?.value;
  if (typeof value !== "number") return null;
  return (
    <g>
      <text x={x - 8} y={y} textAnchor="end" fill="hsl(var(--foreground) / 0.7)" fontSize={11} dy="0.35em">
        {value.toFixed(1)}
      </text>
      {value === -1 ? (
        <text x={x - 8} y={y + 16} textAnchor="end" fill="hsl(var(--foreground) / 0.7)" fontSize={10}>
          AC1
        </text>
      ) : null}
    </g>
  );
};

const RightAxisTick: React.FC<any> = ({ x = 0, y = 0, payload }) => {
  const value = payload?.value;
  if (typeof value !== "number") return null;
  return (
    <g>
      <text x={x + 8} y={y} textAnchor="start" fill="hsl(var(--foreground) / 0.7)" fontSize={11} dy="0.35em">
        {value}%
      </text>
      {value === 0 ? (
        <text x={x + 8} y={y + 16} textAnchor="start" fill="hsl(var(--foreground) / 0.7)" fontSize={10}>
          Acc
        </text>
      ) : null}
    </g>
  );
};

const MetricLegend: React.FC<{ metrics: MetricKey[] }> = ({ metrics }) => {
  if (!metrics.length) return null;

  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 pt-1 text-[11px] text-foreground">
      {metrics.map((key) => {
        const isAccuracy = key.endsWith("_accuracy");
        const color = chartConfig[key].color;
        return (
          <div key={key} className="flex items-center gap-1.5">
            {isAccuracy ? (
              <svg width={10} height={10}><rect x={1} y={1} width={8} height={8} fill={color} /></svg>
            ) : (
              <svg width={10} height={10}><circle cx={5} cy={5} r={4} fill={color} /></svg>
            )}
            <span>{chartConfig[key].label}</span>
          </div>
        );
      })}
    </div>
  );
};

const ChampionTransitionMarkers: React.FC<{
  chartData: ChartPoint[];
  xAxisMap?: Record<string, any>;
  offset?: { top?: number; height?: number };
}> = ({ chartData, xAxisMap, offset }) => {
  if (!chartData.length) return null;

  const xAxis = Object.values(xAxisMap || {})[0] as any;
  const scale = xAxis?.scale;
  if (typeof scale !== "function") return null;

  const y = (offset?.top || 0) + (offset?.height || 0) + 30;

  return (
    <g data-testid="champion-transition-marker-layer" aria-label="Champion changes">
      {chartData.map((point) => {
        const x = scale(point.entered_at_timestamp);
        if (typeof x !== "number" || Number.isNaN(x)) return null;

        return (
          <rect
            key={`${point.version_id}-${point.entered_at}`}
            data-testid="champion-transition-marker"
            x={x - 10}
            y={y}
            width={20}
            height={8}
            rx={4}
            fill="hsl(var(--muted))"
            aria-label={`Champion changed to ${shortId(point.version_id)} on ${formatDateTime(point.entered_at)}`}
          >
            <title>{`${formatDateTime(point.entered_at)}: ${shortId(point.version_id)}`}</title>
          </rect>
        );
      })}
    </g>
  );
};

const TimelineTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload as any;
  if (!point) return null;

  return (
    <div className="rounded-md bg-popover p-3 text-popover-foreground text-xs space-y-1">
      <div className="font-medium">{point.version_note || shortId(point.version_id)}</div>
      <div className="text-muted-foreground">{formatDateTime(point.entered_at)}</div>
      <div>Version: {shortId(point.version_id)}</div>
      <div>Previous champion: {shortId(point.previous_champion_version_id)}</div>
      <div>Feedback AC1: {formatNumber(point.feedback_alignment)}</div>
      <div>Feedback accuracy: {formatAccuracy(point.feedback_accuracy)}</div>
      <div>Regression AC1: {formatNumber(point.regression_alignment)}</div>
      <div>Regression accuracy: {formatAccuracy(point.regression_accuracy)}</div>
      {point.feedback_evaluation_id ? <div>Feedback eval: {shortId(point.feedback_evaluation_id)}</div> : null}
      {point.regression_evaluation_id ? <div>Regression eval: {shortId(point.regression_evaluation_id)}</div> : null}
    </div>
  );
};

const buildChartData = (score: ChampionScoreSeries): ChartPoint[] => {
  return (score.points || [])
    .map((point) => {
      const timestamp = new Date(point.entered_at).getTime();
      return {
        ...point,
        entered_at_timestamp: Number.isFinite(timestamp) ? timestamp : 0,
        feedback_alignment: point.feedback_metrics?.alignment ?? null,
        regression_alignment: point.regression_metrics?.alignment ?? null,
        feedback_accuracy: chartAccuracy(point.feedback_metrics?.accuracy),
        regression_accuracy: chartAccuracy(point.regression_metrics?.accuracy),
      };
    })
    .filter((point) => point.entered_at_timestamp > 0)
    .sort((left, right) => left.entered_at_timestamp - right.entered_at_timestamp);
};

const availableMetricsFor = (chartData: ChartPoint[]): MetricKey[] => {
  return metricKeys.filter((key) =>
    chartData.some((point) => {
      const value = point[key];
      return typeof value === "number" && Number.isFinite(value);
    })
  );
};

const hasMetricChange = (change?: MetricChange | null): boolean => {
  return (
    typeof change?.before === "number" &&
    Number.isFinite(change.before) &&
    typeof change.after === "number" &&
    Number.isFinite(change.after)
  );
};

const selectedPerformanceDataset = (
  summary?: PerformanceSummary | null
): { label: string; dataset: DatasetPerformanceSummary } | null => {
  if (summary?.feedback && (hasMetricChange(summary.feedback.alignment) || hasMetricChange(summary.feedback.accuracy))) {
    return { label: "Feedback", dataset: summary.feedback };
  }
  if (summary?.regression && (hasMetricChange(summary.regression.alignment) || hasMetricChange(summary.regression.accuracy))) {
    return { label: "Regression", dataset: summary.regression };
  }
  return null;
};

const PerformanceGaugeCard: React.FC<{
  title: "Alignment" | "Accuracy";
  change?: MetricChange | null;
}> = ({ title, change }) => {
  if (!hasMetricChange(change)) return null;

  const isAccuracy = title === "Accuracy";
  const before = isAccuracy ? chartAccuracy(change?.before) : change?.before;
  const after = isAccuracy ? chartAccuracy(change?.after) : change?.after;
  if (before === null || before === undefined || after === null || after === undefined) return null;

  const delta = after - before;
  const deltaClassName = delta >= 0 ? "text-green-500" : "text-red-500";

  return (
    <div className="rounded-md bg-card p-3" data-testid={`performance-gauge-${title.toLowerCase()}`}>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <div className="text-sm font-medium">{title}</div>
        <div className={`text-sm font-semibold ${deltaClassName}`}>
          {isAccuracy ? formatSignedAccuracyDelta(delta) : formatSignedNumber(delta, 3)}
        </div>
      </div>
      <div className="flex justify-center">
        <div className="w-[190px]">
          <Gauge
            value={after}
            beforeValue={before}
            showComparisonLabel
            title={title}
            valueUnit={isAccuracy ? "%" : ""}
            min={isAccuracy ? 0 : -1}
            max={isAccuracy ? 100 : 1}
            decimalPlaces={isAccuracy ? 1 : 2}
            segments={isAccuracy ? accuracyGaugeSegments : ac1GaugeSegments}
            showTicks
          />
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <div className="text-muted-foreground">Original</div>
          <div className="font-medium text-foreground">
            {isAccuracy ? formatAccuracy(before) : formatNumber(before, 3)}
          </div>
        </div>
        <div>
          <div className="text-muted-foreground">Delta</div>
          <div className={`font-medium ${deltaClassName}`}>
            {isAccuracy ? formatSignedAccuracyDelta(delta) : formatSignedNumber(delta, 3)}
          </div>
        </div>
        <div>
          <div className="text-muted-foreground">New</div>
          <div className="font-medium text-foreground">
            {isAccuracy ? formatAccuracy(after) : formatNumber(after, 3)}
          </div>
        </div>
      </div>
    </div>
  );
};

const PerformanceSummarySection: React.FC<{
  summary?: PerformanceSummary | null;
}> = ({ summary }) => {
  const selected = selectedPerformanceDataset(summary);
  if (!selected) return null;

  return (
    <div className="rounded-md bg-background p-3" data-testid="performance-summary">
      <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <div>
          <div className="text-base font-semibold">Performance Improvement</div>
          <div className="text-xs text-muted-foreground">
            Previous champion to latest champion
          </div>
        </div>
        <div className="text-xs font-medium text-muted-foreground">{selected.label} dataset</div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <PerformanceGaugeCard title="Alignment" change={selected.dataset.alignment} />
        <PerformanceGaugeCard title="Accuracy" change={selected.dataset.accuracy} />
      </div>
    </div>
  );
};

const SmeMarkdown: React.FC<{ children: string; testId: string }> = ({ children, testId }) => (
  <div
    data-testid={testId}
    className="rounded-md bg-background p-3 text-sm text-foreground"
  >
    <ReactMarkdown
      remarkPlugins={markdownPlugins}
      className="prose prose-sm max-w-none text-foreground dark:prose-invert
        prose-headings:text-foreground prose-headings:font-semibold
        prose-h1:text-base prose-h2:text-base prose-h3:text-sm
        prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-1
        prose-strong:text-foreground prose-a:text-primary"
    >
      {children}
    </ReactMarkdown>
  </div>
);

const ExpandableSmeMarkdown: React.FC<{
  children: string;
  label: string;
  testId: string;
}> = ({ children, label, testId }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-3">
        <div className="text-xs font-medium text-muted-foreground">{label}</div>
      </div>
      <div className={isExpanded ? "" : "max-h-24 overflow-hidden"}>
        <SmeMarkdown testId={testId}>{children}</SmeMarkdown>
      </div>
      <ExpandCaretControl
        isExpanded={isExpanded}
        onClick={() => setIsExpanded((current) => !current)}
        expandLabel={`Expand ${label}`}
        collapseLabel={`Collapse ${label}`}
      />
    </div>
  );
};

const SmeInformationSection: React.FC<{ sme?: SmeInformation | null }> = ({ sme }) => {
  if (!sme) return null;
  if (!sme.agenda) return null;

  return (
    <div className="rounded-md bg-card p-3">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <div className="text-sm font-medium">SME Information</div>
        <div className="font-mono text-xs text-muted-foreground">{shortId(sme.procedure_id)}</div>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>Status: {sme.procedure_status || "N/A"}</span>
        <span>Updated: {formatDateTime(sme.procedure_updated_at)}</span>
        {sme.generated_at ? <span>Generated: {formatDateTime(sme.generated_at)}</span> : null}
      </div>

      <div className="mt-3 space-y-3">
        <ExpandableSmeMarkdown label="Agenda" testId="sme-agenda-markdown">
          {sme.agenda}
        </ExpandableSmeMarkdown>
        {sme.worksheet ? (
          <ExpandableSmeMarkdown label="Worksheet" testId="sme-worksheet-markdown">
            {sme.worksheet}
          </ExpandableSmeMarkdown>
        ) : null}
      </div>
    </div>
  );
};

const handleDiffEditorMount = (_editor: unknown, monaco: Monaco) => {
  defineCustomMonacoThemes(monaco);
  applyMonacoTheme(monaco);
  setupMonacoThemeWatcher(monaco);
  configureYamlLanguage(monaco);
};

const MonacoDiffPanel: React.FC<{
  language: "yaml" | "markdown";
  original?: string | null;
  modified?: string | null;
  fallbackDiff?: string | null;
  emptyText: string;
}> = ({ language, original, modified, fallbackDiff, emptyText }) => {
  const left = original || "";
  const right = modified || "";

  if (!left && !right) {
    return (
      <pre className="whitespace-pre-wrap rounded-md bg-background p-3 text-xs text-foreground">
        {fallbackDiff || emptyText}
      </pre>
    );
  }

  return (
    <div className="h-[420px] rounded-md bg-background">
      <DiffEditor
        height="100%"
        language={language}
        original={left}
        modified={right}
        onMount={handleDiffEditorMount}
        options={{
          ...getCommonMonacoOptions(),
          readOnly: true,
          renderSideBySide: true,
          automaticLayout: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
        }}
      />
    </div>
  );
};

const ChampionDiffSection: React.FC<{
  diff: VersionDiff;
  scorecardId?: string | null;
  scoreId?: string | null;
}> = ({ diff, scorecardId, scoreId }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const [activeTab, setActiveTab] = React.useState<"code" | "guidelines">("code");
  const leftHref = scoreVersionHref(scorecardId, scoreId, diff.left_version_id);
  const rightHref = scoreVersionHref(scorecardId, scoreId, diff.right_version_id);

  return (
    <div className="rounded-md bg-card p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-sm font-medium">Champion Diff</div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <LinkedShortId
              id={diff.left_version_id}
              href={leftHref}
              label="Open previous champion score version"
            />
            <span>to</span>
            <LinkedShortId
              id={diff.right_version_id}
              href={rightHref}
              label="Open latest champion score version"
            />
          </div>
        </div>
      </div>
      <div className="mt-3">
        <ExpandCaretControl
          isExpanded={isOpen}
          onClick={() => setIsOpen((current) => !current)}
          expandLabel="Expand champion diff"
          collapseLabel="Collapse champion diff"
        />
      </div>

      {isOpen ? (
        diff.message ? (
          <div className="mt-3 rounded-md bg-background p-3 text-sm text-foreground">{diff.message}</div>
        ) : (
          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as "code" | "guidelines")}>
            <TabsList className="mt-3">
              <TabsTrigger value="code">Code</TabsTrigger>
              <TabsTrigger value="guidelines">Guidelines</TabsTrigger>
            </TabsList>
            {activeTab === "code" ? (
              <TabsContent value="code">
                <MonacoDiffPanel
                  language="yaml"
                  original={diff.configuration_left}
                  modified={diff.configuration_right}
                  fallbackDiff={diff.configuration_diff}
                  emptyText="No code changes."
                />
              </TabsContent>
            ) : null}
            {activeTab === "guidelines" ? (
              <TabsContent value="guidelines">
                <MonacoDiffPanel
                  language="markdown"
                  original={diff.guidelines_left}
                  modified={diff.guidelines_right}
                  fallbackDiff={diff.guidelines_diff}
                  emptyText="No guideline changes."
                />
              </TabsContent>
            ) : null}
          </Tabs>
        )
      ) : null}
    </div>
  );
};

const ScoreTimelineSection: React.FC<{
  score: ChampionScoreSeries;
  xDomain: [number, number] | undefined;
  scorecardId?: string | null;
}> = ({ score, xDomain, scorecardId }) => {
  const chartData = React.useMemo(() => buildChartData(score), [score]);
  const availableMetricKeys = React.useMemo(() => availableMetricsFor(chartData), [chartData]);
  const currentScoreHref = scoreHref(scorecardId, score.score_id);
  const championChangeCount = score.champion_change_count ?? (score.points || []).filter(
    (point) => Boolean(point.previous_champion_version_id)
  ).length;
  const newChampionCount = score.new_champion_count ?? (score.points || []).filter(
    (point) => !point.previous_champion_version_id
  ).length;

  return (
    <section className="space-y-3 rounded-md bg-muted px-4 pb-4 pt-0">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold">{score.score_name}</h3>
          <div className="text-xs text-muted-foreground">
            {championChangeCount} champion change{championChangeCount === 1 ? "" : "s"}
            {newChampionCount > 0
              ? `, ${newChampionCount} new champion${newChampionCount === 1 ? "" : "s"}`
              : ""}
          </div>
        </div>
        <LinkedShortId
          id={score.score_id}
          href={currentScoreHref}
          label="Open score"
          className="text-xs text-muted-foreground"
          iconSize="md"
        />
      </div>

      <PerformanceSummarySection summary={score.performance_summary} />

      <div className="grid gap-2 sm:grid-cols-4">
        <div className="rounded-md bg-card p-3">
          <div className="text-xs text-muted-foreground">Procedures</div>
          <div className="text-lg font-semibold">{formatInteger(score.optimization_summary?.procedure_count)}</div>
        </div>
        <div className="rounded-md bg-card p-3">
          <div className="text-xs text-muted-foreground">Evaluations</div>
          <div className="text-lg font-semibold">{formatInteger(score.optimization_summary?.evaluation_count)}</div>
        </div>
        <div className="rounded-md bg-card p-3">
          <div className="text-xs text-muted-foreground">Score Results</div>
          <div className="text-lg font-semibold">{formatInteger(score.optimization_summary?.score_result_count)}</div>
        </div>
        <div className="rounded-md bg-card p-3">
          <div className="text-xs text-muted-foreground">Optimization Cost</div>
          <div className="text-lg font-semibold">
            {formatCurrency(score.optimization_summary?.optimization_cost?.overall)}
          </div>
        </div>
      </div>

      {chartData.length > 0 ? (
        <div className="rounded-md bg-background p-2">
          <ChartContainer config={chartConfig} className="h-[260px] w-full">
            <LineChart data={chartData} margin={chartMargin}>
              <CartesianGrid stroke="hsl(var(--foreground) / 0.12)" strokeDasharray="3 3" />
              <XAxis
                dataKey="entered_at_timestamp"
                type="number"
                domain={xDomain || ["dataMin", "dataMax"]}
                tickFormatter={formatAxisDate}
                tick={{ fill: "hsl(var(--foreground) / 0.7)", fontSize: 10 }}
                axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                tickMargin={4}
                padding={{ left: 28, right: 28 }}
              />
              <YAxis
                yAxisId="alignment"
                domain={[-1, 1]}
                ticks={[-1, -0.5, 0, 0.5, 1]}
                axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                tick={<LeftAxisTick />}
                width={52}
              />
              <YAxis
                yAxisId="accuracy"
                orientation="right"
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                tick={<RightAxisTick />}
                width={56}
              />
              <Tooltip content={<TimelineTooltip />} />
              <Customized component={<ChampionTransitionMarkers chartData={chartData} />} />
              {availableMetricKeys.includes("feedback_alignment") ? (
                <Line
                  yAxisId="alignment"
                  type="monotone"
                  dataKey="feedback_alignment"
                  name="Feedback AC1"
                  stroke={chartConfig.feedback_alignment.color}
                  strokeWidth={2}
                  dot={<CircleDot fill={chartConfig.feedback_alignment.color} />}
                  activeDot={{ r: 6 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ) : null}
              {availableMetricKeys.includes("regression_alignment") ? (
                <Line
                  yAxisId="alignment"
                  type="monotone"
                  dataKey="regression_alignment"
                  name="Regression AC1"
                  stroke={chartConfig.regression_alignment.color}
                  strokeWidth={2}
                  dot={<CircleDot fill={chartConfig.regression_alignment.color} />}
                  activeDot={{ r: 6 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ) : null}
              {availableMetricKeys.includes("feedback_accuracy") ? (
                <Line
                  yAxisId="accuracy"
                  type="monotone"
                  dataKey="feedback_accuracy"
                  name="Feedback Accuracy"
                  stroke={chartConfig.feedback_accuracy.color}
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={<SquareDot fill={chartConfig.feedback_accuracy.color} />}
                  activeDot={{ r: 6 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ) : null}
              {availableMetricKeys.includes("regression_accuracy") ? (
                <Line
                  yAxisId="accuracy"
                  type="monotone"
                  dataKey="regression_accuracy"
                  name="Regression Accuracy"
                  stroke={chartConfig.regression_accuracy.color}
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={<SquareDot fill={chartConfig.regression_accuracy.color} />}
                  activeDot={{ r: 6 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ) : null}
            </LineChart>
          </ChartContainer>
          <MetricLegend metrics={availableMetricKeys} />
        </div>
      ) : (
        <div className="rounded-md bg-card p-4 text-sm text-foreground">
          No parseable champion transition dates for this score.
        </div>
      )}

      {score.points?.length ? (
        <div
          data-testid={`version-table-${score.score_id}`}
          className="h-auto max-h-none self-start overflow-visible rounded-md bg-background"
        >
          <div
            role="table"
            aria-label={`${score.score_name} champion versions`}
            className="w-full text-sm"
          >
            <div
              role="row"
              className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,0.8fr)_minmax(0,0.8fr)_minmax(0,1fr)] bg-card text-xs text-muted-foreground"
            >
              <div role="columnheader" className="px-3 py-2 font-medium">Champion Entered</div>
              <div role="columnheader" className="px-3 py-2 font-medium">Version</div>
              <div role="columnheader" className="px-3 py-2 font-medium">Feedback AC1</div>
              <div role="columnheader" className="px-3 py-2 font-medium">Regression AC1</div>
              <div role="columnheader" className="px-3 py-2 font-medium">Previous Champion</div>
            </div>
            {score.points.map((point, index) => (
              <div
                key={`${score.score_id}-${point.version_id}-${point.entered_at}`}
                role="row"
                className={`grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,0.8fr)_minmax(0,0.8fr)_minmax(0,1fr)] ${index % 2 === 0 ? "bg-background" : "bg-muted"}`}
              >
                <div role="cell" className="min-w-0 truncate px-3 py-2">{formatDateTime(point.entered_at)}</div>
                <div role="cell" className="px-3 py-2 text-xs">
                  <LinkedShortId
                    id={point.version_id}
                    href={scoreVersionHref(scorecardId, score.score_id, point.version_id)}
                    label="Open score version"
                  />
                </div>
                <div role="cell" className="px-3 py-2">{formatNumber(point.feedback_metrics?.alignment)}</div>
                <div role="cell" className="px-3 py-2">{formatNumber(point.regression_metrics?.alignment)}</div>
                <div role="cell" className="px-3 py-2 text-xs">
                  <LinkedShortId
                    id={point.previous_champion_version_id}
                    href={scoreVersionHref(scorecardId, score.score_id, point.previous_champion_version_id)}
                    label="Open previous champion score version"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {score.diff ? (
        <ChampionDiffSection diff={score.diff} scorecardId={scorecardId} scoreId={score.score_id} />
      ) : null}

      <SmeInformationSection sme={score.sme} />
    </section>
  );
};

const ScoreChampionVersionTimeline: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<ScoreChampionVersionTimelineData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);
  const isProcessing = Boolean((props.config as any)?.isProcessing);

  let parsedOutput: ScoreChampionVersionTimelineData = {};
  try {
    parsedOutput =
      typeof props.output === "string"
        ? (parseOutputString(props.output) as ScoreChampionVersionTimelineData)
        : ((props.output || {}) as ScoreChampionVersionTimelineData);
  } catch {
    parsedOutput = {};
  }

  React.useEffect(() => {
    if (!parsedOutput.output_compacted || !parsedOutput.output_attachment || loadedOutput) return;

    let cancelled = false;
    setAttachmentLoadError(null);

    (async () => {
      try {
        const result = await downloadData({
          path: parsedOutput.output_attachment!,
          options: { bucket: "reportBlockDetails" as any },
        }).result;
        const text = await result.body.text();
        if (!cancelled) setLoadedOutput(parseOutputString(text) as ScoreChampionVersionTimelineData);
      } catch (error) {
        if (!cancelled) {
          setAttachmentLoadError(
            error instanceof Error ? error.message : "Failed to load compacted output attachment."
          );
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loadedOutput, parsedOutput.output_attachment, parsedOutput.output_compacted]);

  const output = loadedOutput ?? parsedOutput;
  const scores = React.useMemo(
    () => (Array.isArray(output.scores) ? output.scores : []),
    [output.scores]
  );
  const isLoadingCompactedOutput =
    Boolean(parsedOutput.output_compacted) && !loadedOutput && !attachmentLoadError;
  const hasResolvedData =
    scores.length > 0 ||
    Boolean(output.summary) ||
    Boolean(output.message) ||
    Boolean(output.error) ||
    Boolean(output.warning);
  const title =
    props.name && !props.name.startsWith("block_")
      ? props.name
      : output.block_title || "Score Champion Version Timeline";

  const sharedXDomain = React.useMemo<[number, number] | undefined>(() => {
    const start = output.date_range?.start ? new Date(output.date_range.start).getTime() : NaN;
    const end = output.date_range?.end ? new Date(output.date_range.end).getTime() : NaN;
    if (Number.isFinite(start) && Number.isFinite(end) && end > start) {
      return [start, end];
    }
    const timestamps = scores.flatMap((score) =>
      (score.points || [])
        .map((point) => new Date(point.entered_at).getTime())
        .filter((value) => Number.isFinite(value))
    );
    if (!timestamps.length) return undefined;
    return [Math.min(...timestamps), Math.max(...timestamps)];
  }, [output.date_range?.end, output.date_range?.start, scores]);

  if ((isProcessing || isLoadingCompactedOutput) && !hasResolvedData) {
    return (
      <ReportBlock
        {...props}
        output={output as any}
        title={title}
        subtitle={output.block_description}
        error={attachmentLoadError || output.error}
        warning={output.warning}
        dateRange={output.date_range}
      >
        <div className="rounded-md bg-card p-4 text-sm text-foreground">
          Report block is processing. Champion version metrics will appear when computation completes.
        </div>
      </ReportBlock>
    );
  }

  return (
    <ReportBlock
      {...props}
      output={output as any}
      title={title}
      subtitle={output.block_description}
      error={attachmentLoadError || output.error}
      warning={output.warning}
      dateRange={output.date_range}
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Scores With Changes</div>
            <div className="text-xl font-semibold">
              {formatInteger(output.summary?.scores_with_champion_changes ?? scores.length)}
            </div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Champion Changes</div>
            <div className="text-xl font-semibold">{formatInteger(output.summary?.champion_change_count)}</div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Optimization Cost</div>
            <div className="text-xl font-semibold">{formatCurrency(output.summary?.optimization_cost?.overall)}</div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Procedures</div>
            <div className="text-xl font-semibold">{formatInteger(output.summary?.procedure_count)}</div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Evaluations</div>
            <div className="text-xl font-semibold">{formatInteger(output.summary?.evaluation_count)}</div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Score Results</div>
            <div className="text-xl font-semibold">{formatInteger(output.summary?.score_result_count)}</div>
          </div>
        </div>

        <div className="text-sm text-foreground">
          {output.scorecard_name ? `Scorecard: ${output.scorecard_name}` : null}
        </div>

        {scores.length > 0 ? (
          <div className="space-y-4">
            {scores.map((score) => (
              <ScoreTimelineSection
                key={score.score_id}
                score={score}
                xDomain={sharedXDomain}
                scorecardId={output.scorecard_id}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-md bg-card p-4 text-sm text-foreground">
            {output.message || "No champion version changes found in the requested time window."}
          </div>
        )}
      </div>
    </ReportBlock>
  );
};

(ScoreChampionVersionTimeline as BlockComponent).blockClass = "ScoreChampionVersionTimeline";

export default ScoreChampionVersionTimeline;

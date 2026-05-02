"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

import { parseOutputString } from "@/lib/utils";
import { ChartContainer } from "@/components/ui/chart";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ReportBlock, { ReportBlockProps, type BlockComponent } from "./ReportBlock";

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
  configuration_diff?: string | null;
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

interface ChampionScoreSeries {
  score_id: string;
  score_name: string;
  optimization_summary?: OptimizationSummary | null;
  points: ChampionPoint[];
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
  };
  scores?: ChampionScoreSeries[];
  summary?: {
    scores_analyzed?: number;
    scores_with_champion_changes?: number;
    champion_change_count?: number;
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
  feedback_accuracy: { label: "Feedback Accuracy", color: "var(--true)" },
  regression_accuracy: { label: "Regression Accuracy", color: "var(--false)" },
};

const metricKeys = [
  "feedback_alignment",
  "regression_alignment",
  "feedback_accuracy",
  "regression_accuracy",
] as const;

type MetricKey = (typeof metricKeys)[number];

type ChartPoint = ChampionPoint & {
  entered_at_timestamp: number;
  timeline_marker: number;
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

const TimelineTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload as any;
  if (!point) return null;

  return (
    <div className="rounded-md border bg-background p-3 shadow-lg text-xs space-y-1">
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
        timeline_marker: 0,
        feedback_alignment: point.feedback_metrics?.alignment ?? null,
        regression_alignment: point.regression_metrics?.alignment ?? null,
        feedback_accuracy: point.feedback_metrics?.accuracy ?? null,
        regression_accuracy: point.regression_metrics?.accuracy ?? null,
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

const ScoreTimelineSection: React.FC<{
  score: ChampionScoreSeries;
  xDomain: [number, number] | undefined;
}> = ({ score, xDomain }) => {
  const chartData = React.useMemo(() => buildChartData(score), [score]);
  const availableMetricKeys = React.useMemo(() => availableMetricsFor(chartData), [chartData]);

  return (
    <section className="space-y-3 rounded-md border bg-card/40 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <div>
          <h3 className="text-base font-semibold">{score.score_name}</h3>
          <div className="text-xs text-muted-foreground">
            {score.points?.length ?? 0} champion change{(score.points?.length ?? 0) === 1 ? "" : "s"}
          </div>
        </div>
        <div className="font-mono text-xs text-muted-foreground">{shortId(score.score_id)}</div>
      </div>

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
          <div className="text-xs text-muted-foreground">
            Eval records: {formatCurrency(score.optimization_summary?.associated_evaluation_cost)}
          </div>
        </div>
      </div>

      {chartData.length > 0 ? (
        <ChartContainer config={chartConfig} className="h-[260px] w-full">
          <LineChart data={chartData} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey="entered_at_timestamp"
              type="number"
              domain={xDomain || ["dataMin", "dataMax"]}
              tickFormatter={formatAxisDate}
              tickLine={false}
              axisLine={false}
              tickMargin={8}
            />
            <YAxis
              yAxisId="alignment"
              domain={[-1, 1]}
              tickLine={false}
              axisLine={false}
              width={42}
            />
            <YAxis
              yAxisId="accuracy"
              orientation="right"
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <Tooltip content={<TimelineTooltip />} />
            <Line
              yAxisId="alignment"
              type="linear"
              dataKey="timeline_marker"
              name="Champion Version"
              stroke="transparent"
              dot={{ r: 5, fill: "var(--foreground)", strokeWidth: 0 }}
              activeDot={{ r: 7 }}
              isAnimationActive={false}
            />
            {availableMetricKeys.includes("feedback_alignment") ? (
              <Line
                yAxisId="alignment"
                type="monotone"
                dataKey="feedback_alignment"
                name="Feedback AC1"
                stroke={chartConfig.feedback_alignment.color}
                strokeWidth={2}
                connectNulls
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
                connectNulls
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
                connectNulls
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
                connectNulls
              />
            ) : null}
          </LineChart>
        </ChartContainer>
      ) : (
        <div className="rounded-md bg-card p-4 text-sm text-muted-foreground">
          No parseable champion transition dates for this score.
        </div>
      )}

      {score.points?.length ? (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-card text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Champion Entered</th>
                <th className="px-3 py-2 text-left font-medium">Version</th>
                <th className="px-3 py-2 text-left font-medium">Feedback AC1</th>
                <th className="px-3 py-2 text-left font-medium">Regression AC1</th>
                <th className="px-3 py-2 text-left font-medium">Previous Champion</th>
              </tr>
            </thead>
            <tbody>
              {score.points.map((point) => (
                <tr key={`${score.score_id}-${point.version_id}-${point.entered_at}`} className="border-t">
                  <td className="px-3 py-2">{formatDateTime(point.entered_at)}</td>
                  <td className="px-3 py-2 font-mono text-xs">{shortId(point.version_id)}</td>
                  <td className="px-3 py-2">{formatNumber(point.feedback_metrics?.alignment)}</td>
                  <td className="px-3 py-2">{formatNumber(point.regression_metrics?.alignment)}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {shortId(point.previous_champion_version_id)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {score.diff ? (
        <div className="rounded-md bg-card p-3">
          <div className="mb-3 text-sm font-medium">Champion Diff</div>
          <div className="mb-3 text-xs text-muted-foreground">
            {shortId(score.diff.left_version_id)} to {shortId(score.diff.right_version_id)}
          </div>
          {score.diff.message ? (
            <div className="text-sm text-muted-foreground">{score.diff.message}</div>
          ) : (
            <Tabs defaultValue="code">
              <TabsList>
                <TabsTrigger value="code">Code</TabsTrigger>
                <TabsTrigger value="guidelines">Guidelines</TabsTrigger>
              </TabsList>
              <TabsContent value="code">
                <pre className="max-h-96 overflow-auto rounded-md bg-background p-3 text-xs">
                  {score.diff.configuration_diff || "No code changes."}
                </pre>
              </TabsContent>
              <TabsContent value="guidelines">
                <pre className="max-h-96 overflow-auto rounded-md bg-background p-3 text-xs">
                  {score.diff.guidelines_diff || "No guideline changes."}
                </pre>
              </TabsContent>
            </Tabs>
          )}
        </div>
      ) : null}
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
        <div className="rounded-md bg-card p-4 text-sm text-muted-foreground">
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
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Scores Analyzed</div>
            <div className="text-xl font-semibold">{formatInteger(output.summary?.scores_analyzed)}</div>
          </div>
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
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Evaluation Record Cost</div>
            <div className="text-xl font-semibold">{formatCurrency(output.summary?.associated_evaluation_cost)}</div>
          </div>
        </div>

        <div className="text-sm text-muted-foreground">
          {output.scorecard_name ? `Scorecard: ${output.scorecard_name}` : null}
        </div>

        {scores.length > 0 ? (
          <div className="space-y-4">
            {scores.map((score) => (
              <ScoreTimelineSection key={score.score_id} score={score} xDomain={sharedXDomain} />
            ))}
          </div>
        ) : (
          <div className="rounded-md bg-card p-4 text-sm text-muted-foreground">
            {output.message || "No champion version changes found in the requested time window."}
          </div>
        )}
      </div>
    </ReportBlock>
  );
};

(ScoreChampionVersionTimeline as BlockComponent).blockClass = "ScoreChampionVersionTimeline";

export default ScoreChampionVersionTimeline;

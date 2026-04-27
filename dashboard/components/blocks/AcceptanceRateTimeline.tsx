"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

import { parseOutputString } from "@/lib/utils";
import { ChartContainer } from "@/components/ui/chart";
import ReportBlock, { ReportBlockProps, type BlockComponent } from "./ReportBlock";

interface AcceptanceTimelinePoint {
  bucket_index: number;
  label: string;
  start: string;
  end: string;
  total_score_results: number;
  accepted_score_results: number;
  corrected_score_results: number;
  score_result_acceptance_rate: number;
  feedback_items_total: number;
  feedback_items_valid: number;
  feedback_items_changed: number;
  score_results_with_feedback: number;
}

interface AcceptanceRateTimelineData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
  show_bucket_details?: boolean;
  scorecard_name?: string;
  score_name?: string | null;
  date_range?: {
    start: string;
    end: string;
  };
  bucket_policy?: {
    bucket_type?: string;
    bucket_count?: number;
    bucket_days?: number;
    timezone?: string;
  };
  points?: AcceptanceTimelinePoint[];
  summary?: {
    total_score_results: number;
    accepted_score_results: number;
    corrected_score_results: number;
    score_result_acceptance_rate: number;
    feedback_items_total: number;
    feedback_items_valid: number;
    feedback_items_changed: number;
    score_results_with_feedback: number;
  };
  message?: string;
  warning?: string;
  error?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

const ACCEPTANCE_COLOR = "#16a34a";

const chartConfig = {
  acceptance: {
    label: "Score Result Acceptance Rate",
    color: ACCEPTANCE_COLOR,
  },
};

const formatPercent = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "0.00%";
  return `${(value * 100).toFixed(2)}%`;
};

const TimelineTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload as AcceptanceTimelinePoint | undefined;
  if (!point) return null;

  const start = new Date(point.start);
  const end = new Date(point.end);

  return (
    <div className="rounded-md border bg-background p-3 shadow-lg text-xs space-y-1">
      <div className="font-medium">{point.label}</div>
      <div className="text-muted-foreground">
        {start.toLocaleString()} - {end.toLocaleString()}
      </div>
      <div>Score Result Acceptance Rate: {formatPercent(point.score_result_acceptance_rate)}</div>
      <div>
        Accepted: {point.accepted_score_results} / {point.total_score_results}
      </div>
      <div>Corrected: {point.corrected_score_results}</div>
      <div>
        Feedback edits: {point.feedback_items_valid}/{point.feedback_items_total}
      </div>
      <div>Value-changing edits: {point.feedback_items_changed}</div>
      <div>Score results with any feedback: {point.score_results_with_feedback}</div>
    </div>
  );
};

const AcceptanceRateTimeline: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<AcceptanceRateTimelineData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);
  const isProcessing = Boolean((props.config as any)?.isProcessing);

  let parsedOutput: AcceptanceRateTimelineData = {};
  try {
    parsedOutput =
      typeof props.output === "string"
        ? (parseOutputString(props.output) as AcceptanceRateTimelineData)
        : ((props.output || {}) as AcceptanceRateTimelineData);
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
        if (!cancelled) setLoadedOutput(parseOutputString(text) as AcceptanceRateTimelineData);
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
  const points = Array.isArray(output.points) ? output.points : [];
  const summary = output.summary;
  const showBucketDetails = Boolean(output.show_bucket_details);
  const isLoadingCompactedOutput =
    Boolean(parsedOutput.output_compacted) && !loadedOutput && !attachmentLoadError;
  const hasResolvedData =
    points.length > 0 ||
    Boolean(summary) ||
    Boolean(output.error) ||
    Boolean(output.warning);
  const title =
    props.name && !props.name.startsWith("block_")
      ? props.name
      : output.block_title || "Acceptance Rate Timeline";

  const data = points.map((point) => ({
    ...point,
    acceptance: point.score_result_acceptance_rate,
  }));

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
          Report block is processing. Timeline metrics will appear when computation completes.
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
            <div className="text-xs text-muted-foreground">Score-Result Acceptance Rate</div>
            <div className="text-xl font-semibold">
              {formatPercent(summary?.score_result_acceptance_rate)}
            </div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Accepted Score Results</div>
            <div className="text-xl font-semibold">
              {(summary?.accepted_score_results ?? 0)} / {(summary?.total_score_results ?? 0)}
            </div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Feedback Edits</div>
            <div className="text-xl font-semibold">{summary?.feedback_items_total ?? 0}</div>
            <div className="text-xs text-muted-foreground">
              Valid: {summary?.feedback_items_valid ?? 0}
            </div>
            <div className="text-xs text-muted-foreground">
              Value changed: {summary?.feedback_items_changed ?? 0}
            </div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Score Results With Feedback</div>
            <div className="text-xl font-semibold">{summary?.score_results_with_feedback ?? 0}</div>
          </div>
        </div>

        <div className="text-sm text-muted-foreground">
          {output.scorecard_name ? `Scorecard: ${output.scorecard_name}` : null}
          {output.score_name ? ` • Score: ${output.score_name}` : null}
          {output.bucket_policy?.bucket_type ? ` • Buckets: ${output.bucket_policy.bucket_type}` : null}
          {summary ? ` • Feedback edits: ${summary.feedback_items_valid ?? 0}/${summary.feedback_items_total ?? 0}` : null}
          {summary ? ` • Value-changing edits: ${summary.feedback_items_changed ?? 0}` : null}
        </div>

        <div className="rounded-md bg-card p-3">
          <ChartContainer config={chartConfig} className="h-[280px] w-full">
            <LineChart data={data} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={18} />
              <YAxis
                domain={[0, 1]}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `${Math.round(v * 100)}%`}
              />
              <Tooltip content={<TimelineTooltip />} />
              <Line
                type="monotone"
                dataKey="acceptance"
                stroke={ACCEPTANCE_COLOR}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ChartContainer>
        </div>

        {showBucketDetails && (
          <div className="rounded-md bg-card p-3">
            <div className="mb-2 text-sm font-medium">Bucket Metrics</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th className="px-2 py-1 font-medium">Bucket</th>
                    <th className="px-2 py-1 font-medium">Window</th>
                    <th className="px-2 py-1 font-medium">Acceptance</th>
                    <th className="px-2 py-1 font-medium">Accepted / Total</th>
                    <th className="px-2 py-1 font-medium">Corrected</th>
                    <th className="px-2 py-1 font-medium">Feedback (valid/total)</th>
                    <th className="px-2 py-1 font-medium">Value Changed</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((point) => (
                    <tr key={`${point.bucket_index}-${point.label}`}>
                      <td className="px-2 py-1">{point.label}</td>
                      <td className="px-2 py-1 text-muted-foreground">
                        {new Date(point.start).toLocaleDateString()} - {new Date(point.end).toLocaleDateString()}
                      </td>
                      <td className="px-2 py-1">{formatPercent(point.score_result_acceptance_rate)}</td>
                      <td className="px-2 py-1">
                        {point.accepted_score_results} / {point.total_score_results}
                      </td>
                      <td className="px-2 py-1">{point.corrected_score_results}</td>
                      <td className="px-2 py-1">
                        {point.feedback_items_valid}/{point.feedback_items_total}
                      </td>
                      <td className="px-2 py-1">{point.feedback_items_changed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </ReportBlock>
  );
};

(AcceptanceRateTimeline as BlockComponent).blockClass = "AcceptanceRateTimeline";

export default AcceptanceRateTimeline;

"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

import { parseOutputString } from "@/lib/utils";
import { ChartContainer } from "@/components/ui/chart";
import ReportBlock, { ReportBlockProps, type BlockComponent } from "./ReportBlock";

interface FeedbackVolumeTimelinePoint {
  bucket_index: number;
  label: string;
  start: string;
  end: string;
  feedback_items_total: number;
  feedback_items_valid: number;
  feedback_items_unchanged: number;
  feedback_items_changed: number;
  feedback_items_invalid_or_unclassified: number;
}

interface FeedbackVolumeTimelineData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
  show_bucket_details?: boolean;
  scope?: string;
  scorecard_name?: string;
  score_name?: string | null;
  date_range?: {
    start: string;
    end: string;
  };
  bucket_policy?: {
    bucket_type?: string;
    bucket_count?: number;
    timezone?: string;
    week_start?: string;
  };
  points?: FeedbackVolumeTimelinePoint[];
  summary?: {
    feedback_items_total: number;
    feedback_items_valid: number;
    feedback_items_unchanged: number;
    feedback_items_changed: number;
    feedback_items_invalid_or_unclassified: number;
  };
  message?: string;
  warning?: string;
  error?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

const chartConfig = {
  unchanged: {
    label: "Unchanged",
    color: "var(--true)",
  },
  changed: {
    label: "Changed",
    color: "var(--false)",
  },
  invalid: {
    label: "Invalid / Unclassified",
    color: "var(--progress-background)",
  },
};

const TimelineTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload as FeedbackVolumeTimelinePoint | undefined;
  if (!point) return null;

  const start = new Date(point.start);
  const end = new Date(point.end);

  return (
    <div className="rounded-md border bg-background p-3 shadow-lg text-xs space-y-1">
      <div className="font-medium">{point.label}</div>
      <div className="text-muted-foreground">
        {start.toLocaleString()} - {end.toLocaleString()}
      </div>
      <div>Total feedback items: {point.feedback_items_total}</div>
      <div>Valid feedback items: {point.feedback_items_valid}</div>
      <div>Unchanged: {point.feedback_items_unchanged}</div>
      <div>Changed: {point.feedback_items_changed}</div>
      <div>Invalid / unclassified: {point.feedback_items_invalid_or_unclassified}</div>
    </div>
  );
};

const FeedbackVolumeTimeline: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<FeedbackVolumeTimelineData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);
  const isProcessing = Boolean((props.config as any)?.isProcessing);

  let parsedOutput: FeedbackVolumeTimelineData = {};
  try {
    parsedOutput =
      typeof props.output === "string"
        ? (parseOutputString(props.output) as FeedbackVolumeTimelineData)
        : ((props.output || {}) as FeedbackVolumeTimelineData);
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
        if (!cancelled) setLoadedOutput(parseOutputString(text) as FeedbackVolumeTimelineData);
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
      : output.block_title || "Feedback Volume Timeline";

  const data = points.map((point) => ({
    ...point,
    unchanged: point.feedback_items_unchanged,
    changed: point.feedback_items_changed,
    invalid: point.feedback_items_invalid_or_unclassified,
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
          Report block is processing. Feedback volume metrics will appear when computation completes.
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
            <div className="text-xs text-muted-foreground">Total Feedback Items</div>
            <div className="text-xl font-semibold">{summary?.feedback_items_total ?? 0}</div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Unchanged</div>
            <div className="text-xl font-semibold">{summary?.feedback_items_unchanged ?? 0}</div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Changed</div>
            <div className="text-xl font-semibold">{summary?.feedback_items_changed ?? 0}</div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Invalid / Unclassified</div>
            <div className="text-xl font-semibold">
              {summary?.feedback_items_invalid_or_unclassified ?? 0}
            </div>
          </div>
        </div>

        <div className="text-sm text-muted-foreground">
          {output.scorecard_name ? `Scorecard: ${output.scorecard_name}` : null}
          {output.score_name ? ` • Score: ${output.score_name}` : null}
          {output.bucket_policy?.bucket_type ? ` • Buckets: ${output.bucket_policy.bucket_type}` : null}
          {summary ? ` • Valid feedback items: ${summary.feedback_items_valid ?? 0}` : null}
        </div>

        <div className="rounded-md bg-card p-3">
          <ChartContainer config={chartConfig} className="h-[280px] w-full">
            <BarChart data={data} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={18} />
              <YAxis tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip content={<TimelineTooltip />} />
              <Bar dataKey="unchanged" stackId="feedback" fill="var(--true)" isAnimationActive={false} />
              <Bar dataKey="changed" stackId="feedback" fill="var(--false)" isAnimationActive={false} />
              <Bar dataKey="invalid" stackId="feedback" fill="var(--progress-background)" isAnimationActive={false} />
            </BarChart>
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
                    <th className="px-2 py-1 font-medium">Total</th>
                    <th className="px-2 py-1 font-medium">Valid</th>
                    <th className="px-2 py-1 font-medium">Unchanged</th>
                    <th className="px-2 py-1 font-medium">Changed</th>
                    <th className="px-2 py-1 font-medium">Invalid / Unclassified</th>
                  </tr>
                </thead>
                <tbody>
                  {points.map((point) => (
                    <tr key={`${point.bucket_index}-${point.label}`}>
                      <td className="px-2 py-1">{point.label}</td>
                      <td className="px-2 py-1 text-muted-foreground">
                        {new Date(point.start).toLocaleDateString()} - {new Date(point.end).toLocaleDateString()}
                      </td>
                      <td className="px-2 py-1">{point.feedback_items_total}</td>
                      <td className="px-2 py-1">{point.feedback_items_valid}</td>
                      <td className="px-2 py-1">{point.feedback_items_unchanged}</td>
                      <td className="px-2 py-1">{point.feedback_items_changed}</td>
                      <td className="px-2 py-1">{point.feedback_items_invalid_or_unclassified}</td>
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

(FeedbackVolumeTimeline as BlockComponent).blockClass = "FeedbackVolumeTimeline";

export default FeedbackVolumeTimeline;

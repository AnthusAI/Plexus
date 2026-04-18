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
  score_results_with_feedback: number;
}

interface AcceptanceRateTimelineData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
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
      <div>Score results with any feedback: {point.score_results_with_feedback}</div>
    </div>
  );
};

const AcceptanceRateTimeline: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<AcceptanceRateTimelineData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);

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
  const title =
    props.name && !props.name.startsWith("block_")
      ? props.name
      : output.block_title || "Acceptance Rate Timeline";

  const data = points.map((point) => ({
    ...point,
    acceptance: point.score_result_acceptance_rate,
  }));

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
        <div className="text-sm text-muted-foreground">
          {output.scorecard_name ? `Scorecard: ${output.scorecard_name}` : null}
          {output.score_name ? ` • Score: ${output.score_name}` : null}
          {output.bucket_policy?.bucket_type ? ` • Buckets: ${output.bucket_policy.bucket_type}` : null}
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
      </div>
    </ReportBlock>
  );
};

(AcceptanceRateTimeline as BlockComponent).blockClass = "AcceptanceRateTimeline";

export default AcceptanceRateTimeline;


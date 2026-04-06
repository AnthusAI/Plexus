"use client";

import React from "react";
import { parseOutputString } from "@/lib/utils";
import ReportBlock, { ReportBlockProps, type BlockComponent } from "./ReportBlock";
import { ChartContainer } from "@/components/ui/chart";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CartesianGrid, Legend, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

interface AlignmentPoint {
  bucket_index: number;
  label: string;
  start: string;
  end: string;
  ac1: number | null;
  accuracy: number | null;
  item_count: number;
  agreements: number;
  mismatches: number;
}

interface AlignmentSeries {
  score_id: string;
  score_name: string;
  points: AlignmentPoint[];
}

interface FeedbackAlignmentTimelineData {
  mode?: "single_score" | "all_scores";
  block_title?: string;
  block_description?: string;
  scorecard_id?: string;
  scorecard_name?: string;
  date_range?: {
    start: string;
    end: string;
  };
  bucket_policy?: {
    bucket_type?: string;
    bucket_count?: number;
    timezone?: string;
    week_start?: string;
    complete_only?: boolean;
  };
  overall?: AlignmentSeries;
  scores?: AlignmentSeries[];
  message?: string;
  warning?: string;
  error?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

const OVERALL_SERIES_KEY = "__overall__";

const chartConfig = {
  ac1: {
    label: "AC1",
    color: "hsl(var(--chart-1))",
  },
  accuracy: {
    label: "Accuracy (%)",
    color: "hsl(var(--chart-2))",
  },
};

const formatValue = (value: number | null | undefined, decimals = 2): string => {
  if (value === null || value === undefined) return "N/A";
  return value.toFixed(decimals);
};

const AlignmentTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const point = payload[0]?.payload as AlignmentPoint | undefined;
  if (!point) {
    return null;
  }

  const start = new Date(point.start);
  const end = new Date(point.end);

  return (
    <div className="rounded-md border bg-background p-3 shadow-lg text-xs space-y-1">
      <div className="font-medium">{point.label}</div>
      <div className="text-muted-foreground">
        {start.toLocaleString()} - {end.toLocaleString()}
      </div>
      <div>Items: {point.item_count}</div>
      <div>AC1: {formatValue(point.ac1, 3)}</div>
      <div>Accuracy: {point.accuracy === null || point.accuracy === undefined ? "N/A" : `${formatValue(point.accuracy, 2)}%`}</div>
      <div>Agreements: {point.agreements}</div>
      <div>Mismatches: {point.mismatches}</div>
    </div>
  );
};

const FeedbackAlignmentTimeline: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<FeedbackAlignmentTimelineData | null>(null);
  const [selectedSeries, setSelectedSeries] = React.useState<string>(OVERALL_SERIES_KEY);

  let parsedOutput: FeedbackAlignmentTimelineData = {};
  try {
    if (typeof props.output === "string") {
      parsedOutput = parseOutputString(props.output) as FeedbackAlignmentTimelineData;
    } else {
      parsedOutput = (props.output || {}) as FeedbackAlignmentTimelineData;
    }
  } catch {
    parsedOutput = {};
  }

  React.useEffect(() => {
    if (!parsedOutput.output_compacted || !parsedOutput.output_attachment || loadedOutput) {
      return;
    }

    (async () => {
      try {
        const { downloadData } = await import("aws-amplify/storage");
        const result = await downloadData({
          path: parsedOutput.output_attachment!,
          options: { bucket: "reportBlockDetails" as any },
        }).result;
        const text = await result.body.text();
        setLoadedOutput(parseOutputString(text) as FeedbackAlignmentTimelineData);
      } catch (error) {
        console.warn("FeedbackAlignmentTimeline: failed to load compacted output attachment", error);
      }
    })();
  }, [loadedOutput, parsedOutput.output_attachment, parsedOutput.output_compacted]);

  const data = loadedOutput ?? parsedOutput;
  const title =
    props.name && !props.name.startsWith("block_")
      ? props.name
      : data.block_title || "Feedback Alignment Timeline";

  const scores = React.useMemo<AlignmentSeries[]>(
    () => (Array.isArray(data.scores) ? data.scores : []),
    [data.scores]
  );
  const mode = data.mode || "all_scores";
  const isSingleScoreMode = mode === "single_score";

  React.useEffect(() => {
    if (isSingleScoreMode && scores.length > 0) {
      setSelectedSeries(scores[0].score_id);
      return;
    }

    const validKeys = new Set<string>([OVERALL_SERIES_KEY, ...scores.map((score) => score.score_id)]);
    if (!validKeys.has(selectedSeries)) {
      setSelectedSeries(OVERALL_SERIES_KEY);
    }
  }, [isSingleScoreMode, scores, selectedSeries]);

  const activeSeries = React.useMemo(() => {
    if (isSingleScoreMode) {
      return scores[0] || data.overall || null;
    }
    if (selectedSeries === OVERALL_SERIES_KEY) {
      return data.overall || null;
    }
    return scores.find((score) => score.score_id === selectedSeries) || null;
  }, [data.overall, isSingleScoreMode, scores, selectedSeries]);

  const chartData = activeSeries?.points || [];
  const seriesLabel = activeSeries?.score_name || "Overall";

  const hasChartData = chartData.length > 0;
  const hasSeriesSelector = !isSingleScoreMode && scores.length > 0;

  return (
    <ReportBlock
      {...props}
      output={data as any}
      title={title}
      subtitle={data.block_description}
      warning={data.warning}
      error={data.error}
      dateRange={data.date_range}
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-muted-foreground">
            <div>
              <strong className="text-foreground">Mode:</strong>{" "}
              {isSingleScoreMode ? "Single score" : "All scores on scorecard"}
            </div>
            <div>
              <strong className="text-foreground">Buckets:</strong>{" "}
              {data.bucket_policy?.bucket_count ?? chartData.length} x{" "}
              {data.bucket_policy?.bucket_type || "trailing_7d"} (complete periods only)
            </div>
          </div>

          {hasSeriesSelector && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Series</span>
              <Select value={selectedSeries} onValueChange={setSelectedSeries}>
                <SelectTrigger className="w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={OVERALL_SERIES_KEY}>Overall</SelectItem>
                  {scores.map((score) => (
                    <SelectItem key={score.score_id} value={score.score_id}>
                      {score.score_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        {data.message && <p className="text-xs text-muted-foreground">{data.message}</p>}

        {!hasChartData ? (
          <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
            No bucketed alignment data available for the selected series.
          </div>
        ) : (
          <div className="rounded-md border bg-card p-3">
            <div className="text-sm font-medium mb-2">{seriesLabel}</div>
            <ChartContainer config={chartConfig} className="h-[320px] w-full">
              <LineChart data={chartData} margin={{ top: 12, right: 16, left: 6, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis yAxisId="left" domain={[-1, 1]} tickFormatter={(value) => `${value}`} />
                <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tickFormatter={(value) => `${value}%`} />
                <Tooltip content={<AlignmentTooltip />} />
                <Legend />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="ac1"
                  name="AC1"
                  stroke="var(--color-ac1)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls={false}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="accuracy"
                  name="Accuracy (%)"
                  stroke="var(--color-accuracy)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls={false}
                />
              </LineChart>
            </ChartContainer>
          </div>
        )}
      </div>
    </ReportBlock>
  );
};

(FeedbackAlignmentTimeline as BlockComponent).blockClass = "FeedbackAlignmentTimeline";

export default FeedbackAlignmentTimeline;

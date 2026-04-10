"use client";

import React from "react";
import { parseOutputString } from "@/lib/utils";
import ReportBlock, { ReportBlockProps, type BlockComponent } from "./ReportBlock";
import { ChartContainer } from "@/components/ui/chart";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ac1GaugeSegments } from "@/components/ui/scorecard-evaluation";
import { CartesianGrid, Line, LineChart, ReferenceArea, Tooltip, XAxis, YAxis } from "recharts";

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
const AC1_COLOR = "#2563eb";
const AC1_MIN = -1;
const AC1_MAX = 1;

const chartConfig = {
  ac1: {
    label: "AC1",
    color: AC1_COLOR,
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
      <div>Agreements: {point.agreements}</div>
      <div>Mismatches: {point.mismatches}</div>
    </div>
  );
};

const FeedbackAlignmentTimeline: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<FeedbackAlignmentTimelineData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);
  const [selectedSeries, setSelectedSeries] = React.useState<string>(OVERALL_SERIES_KEY);
  const [isSeriesLoading, setIsSeriesLoading] = React.useState(false);

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

    let cancelled = false;
    setAttachmentLoadError(null);

    (async () => {
      try {
        const { downloadData } = await import("aws-amplify/storage");
        const result = await downloadData({
          path: parsedOutput.output_attachment!,
          options: { bucket: "reportBlockDetails" as any },
        }).result;
        const text = await result.body.text();
        if (!cancelled) {
          setLoadedOutput(parseOutputString(text) as FeedbackAlignmentTimelineData);
        }
      } catch (error) {
        console.warn("FeedbackAlignmentTimeline: failed to load compacted output attachment", error);
        if (!cancelled) {
          const errorMessage =
            error instanceof Error ? error.message : "Failed to load compacted output attachment.";
          setAttachmentLoadError(errorMessage);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadedOutput, parsedOutput.output_attachment, parsedOutput.output_compacted]);

  const data = loadedOutput ?? parsedOutput;
  const isCompactedOutput = Boolean(parsedOutput.output_compacted);
  const isLoadingCompactedOutput = isCompactedOutput && !loadedOutput && !attachmentLoadError;
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

  React.useEffect(() => {
    if (!isSeriesLoading) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setIsSeriesLoading(false);
    }, 180);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [isSeriesLoading, selectedSeries]);

  const handleSeriesChange = React.useCallback(
    (nextSeries: string) => {
      if (nextSeries === selectedSeries) {
        return;
      }
      setIsSeriesLoading(true);
      setSelectedSeries(nextSeries);
    },
    [selectedSeries]
  );

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
  const selectedSeriesLabel = selectedSeries === OVERALL_SERIES_KEY
    ? "Overall"
    : scores.find((score) => score.score_id === selectedSeries)?.score_name || "Selected series";

  const itemCountRange = React.useMemo(() => {
    const counts = chartData
      .filter((point) => point.ac1 !== null && point.ac1 !== undefined && point.item_count > 0)
      .map((point) => point.item_count);
    if (counts.length === 0) {
      return { min: 0, max: 0 };
    }
    return { min: Math.min(...counts), max: Math.max(...counts) };
  }, [chartData]);

  const getDotRadius = React.useCallback(
    (itemCount: number): number => {
      if (!Number.isFinite(itemCount) || itemCount <= 0) {
        return 0;
      }
      if (itemCountRange.max <= itemCountRange.min) {
        return 5;
      }
      const normalized = (itemCount - itemCountRange.min) / (itemCountRange.max - itemCountRange.min);
      return 3 + (normalized * 6);
    },
    [itemCountRange.max, itemCountRange.min]
  );

  const renderAc1Dot = React.useCallback(
    (dotProps: any) => {
      const hiddenDot = <circle cx={0} cy={0} r={0} fill="transparent" stroke="none" />;
      const point = dotProps?.payload as AlignmentPoint | undefined;
      if (!point || point.ac1 === null || point.ac1 === undefined) {
        return hiddenDot;
      }
      const cx = Number(dotProps?.cx);
      const cy = Number(dotProps?.cy);
      if (!Number.isFinite(cx) || !Number.isFinite(cy)) {
        return hiddenDot;
      }
      const radius = getDotRadius(point.item_count);
      if (radius <= 0) {
        return hiddenDot;
      }
      return (
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill={AC1_COLOR}
          fillOpacity={0.9}
          stroke="hsl(var(--background))"
          strokeWidth={1.25}
        />
      );
    },
    [getDotRadius]
  );

  const renderActiveAc1Dot = React.useCallback(
    (dotProps: any) => {
      const hiddenDot = <circle cx={0} cy={0} r={0} fill="transparent" stroke="none" />;
      const point = dotProps?.payload as AlignmentPoint | undefined;
      if (!point || point.ac1 === null || point.ac1 === undefined) {
        return hiddenDot;
      }
      const cx = Number(dotProps?.cx);
      const cy = Number(dotProps?.cy);
      if (!Number.isFinite(cx) || !Number.isFinite(cy)) {
        return hiddenDot;
      }
      const radius = getDotRadius(point.item_count) + 1.5;
      return (
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill={AC1_COLOR}
          fillOpacity={1}
          stroke="hsl(var(--background))"
          strokeWidth={2}
        />
      );
    },
    [getDotRadius]
  );

  const hasChartData = chartData.length > 0;
  const renderableAc1Points = React.useMemo(
    () => chartData.filter((point) => point.ac1 !== null && point.ac1 !== undefined),
    [chartData]
  );
  const ac1YAxisFloor = React.useMemo(() => {
    return renderableAc1Points.some((point) => (point.ac1 ?? 0) < 0) ? AC1_MIN : 0;
  }, [renderableAc1Points]);
  const ac1YAxisDomain = React.useMemo<[number, number]>(
    () => [ac1YAxisFloor, AC1_MAX],
    [ac1YAxisFloor]
  );
  const ac1BackgroundBands = React.useMemo(() => {
    const toAc1Value = (percent: number) => AC1_MIN + ((percent / 100) * (AC1_MAX - AC1_MIN));
    return ac1GaugeSegments.map((segment) => {
      const bandStart = toAc1Value(segment.start);
      const bandEnd = toAc1Value(segment.end);
      return {
        y1: Math.min(bandStart, bandEnd),
        y2: Math.max(bandStart, bandEnd),
        color: segment.color,
      };
    });
  }, []);
  const hasRenderableAc1Points = renderableAc1Points.length > 0;
  const canDrawConnectingLine = renderableAc1Points.length > 1;
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
              {isLoadingCompactedOutput ? "loading..." : data.bucket_policy?.bucket_count ?? chartData.length} x{" "}
              {data.bucket_policy?.bucket_type || "trailing_7d"} (complete periods only)
            </div>
          </div>

          {hasSeriesSelector && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Series</span>
              <Select value={selectedSeries} onValueChange={handleSeriesChange}>
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

        {isLoadingCompactedOutput ? (
          <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
            Loading bucketed alignment data...
          </div>
        ) : isSeriesLoading ? (
          <div className="rounded-md bg-muted/20 p-4 text-sm text-muted-foreground">
            Loading {selectedSeriesLabel}...
          </div>
        ) : attachmentLoadError ? (
          <div className="rounded-md border bg-amber-50 p-4 text-sm text-amber-800">
            Failed to load attached report data: {attachmentLoadError}
          </div>
        ) : !hasChartData ? (
          <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
            No bucketed alignment data available for the selected series.
          </div>
        ) : !hasRenderableAc1Points ? (
          <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
            No AC1 data is available for this series in the selected buckets.
          </div>
        ) : (
          <div className="rounded-md bg-background p-3">
            <div className="text-sm font-medium mb-2">{seriesLabel}</div>
            <ChartContainer config={chartConfig} className="h-[320px] w-full">
              <LineChart data={chartData} margin={{ top: 12, right: 20, left: 0, bottom: 10 }}>
                {ac1BackgroundBands.map((band, index) => (
                  <ReferenceArea
                    key={`ac1-band-${index}`}
                    yAxisId="left"
                    y1={band.y1}
                    y2={band.y2}
                    fill={band.color}
                    fillOpacity={0.22}
                    strokeOpacity={0}
                    ifOverflow="hidden"
                  />
                ))}
                <CartesianGrid stroke="hsl(var(--foreground) / 0.18)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="label"
                  padding={{ left: 0, right: 28 }}
                  interval="preserveStartEnd"
                  axisLine={{ stroke: "hsl(var(--foreground) / 0.35)" }}
                  tickLine={{ stroke: "hsl(var(--foreground) / 0.35)" }}
                  tick={{ fill: "hsl(var(--foreground) / 0.9)", fontSize: 12 }}
                />
                <YAxis
                  yAxisId="left"
                  domain={ac1YAxisDomain}
                  tickFormatter={(value) => `${value}`}
                  axisLine={{ stroke: "hsl(var(--foreground) / 0.35)" }}
                  tickLine={{ stroke: "hsl(var(--foreground) / 0.35)" }}
                  tick={{ fill: "hsl(var(--foreground) / 0.9)", fontSize: 12 }}
                />
                <Tooltip content={<AlignmentTooltip />} />
                <Line
                  yAxisId="left"
                  type="linear"
                  dataKey="ac1"
                  name="AC1"
                  stroke={AC1_COLOR}
                  strokeWidth={3}
                  dot={false}
                  activeDot={false}
                  isAnimationActive={false}
                  connectNulls
                />
                <Line
                  yAxisId="left"
                  type="linear"
                  dataKey="ac1"
                  name="AC1 points"
                  stroke="transparent"
                  strokeWidth={0}
                  dot={renderAc1Dot}
                  activeDot={renderActiveAc1Dot}
                  isAnimationActive={false}
                  connectNulls
                />
              </LineChart>
            </ChartContainer>
            {!canDrawConnectingLine && (
              <p className="mt-2 text-xs text-muted-foreground">
                This series has only one bucket with AC1 data, so there is no line segment to draw yet.
              </p>
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              Dot size indicates the number of feedback items in each bucket.
            </p>
          </div>
        )}
      </div>
    </ReportBlock>
  );
};

(FeedbackAlignmentTimeline as BlockComponent).blockClass = "FeedbackAlignmentTimeline";

export default FeedbackAlignmentTimeline;

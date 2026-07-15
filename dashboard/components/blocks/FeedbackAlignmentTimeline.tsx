"use client";

import React from "react";
import { parseOutputString } from "@/lib/utils";
import ReportBlock, { ReportBlockProps, type BlockComponent } from "./ReportBlock";
import { ChartContainer } from "@/components/ui/chart";
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
  bucket_item_count?: number;
  sample_item_count?: number;
  lookback_item_count?: number;
  sample_start?: string | null;
  sample_end?: string | null;
  sample_extended?: boolean;
  sample_underfilled?: boolean;
}

interface AlignmentSeries {
  score_id: string;
  score_name: string;
  points: AlignmentPoint[];
}

interface SamplePolicy {
  rolling_min_items?: number;
  bucket_type?: string;
  lookback?: string;
  bucket_timestamp?: string;
  prediction_value?: string;
  reference_value?: string;
  explanation?: string;
}

interface FeedbackAlignmentTimelineData {
  mode?: "single_score" | "all_scores";
  block_title?: string;
  block_description?: string;
  show_methodology?: boolean;
  show_bucket_details?: boolean;
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
    window_mode?: "historical_complete" | "exact_window";
  };
  sample_policy?: SamplePolicy;
  fetched_feedback_items?: number;
  ignored_invalid_feedback_items?: number;
  analyzed_feedback_items?: number;
  overall?: AlignmentSeries;
  scores?: AlignmentSeries[];
  message?: string;
  warning?: string;
  error?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

const AC1_COLOR = "#2563eb";
const AC1_MIN = -1;
const AC1_MAX = 1;
const DEFAULT_ROLLING_MIN_ITEMS = 100;

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

const formatDateTime = (value: string | null | undefined): string => {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
};

const formatDateRange = (start: string | null | undefined, end: string | null | undefined): string => {
  if (!start && !end) return "N/A";
  return `${formatDateTime(start)} - ${formatDateTime(end)}`;
};

const getSampleCount = (point: AlignmentPoint): number => point.sample_item_count ?? point.item_count ?? 0;

const getMethodologyItems = (rollingMinItems: number): string[] => [
  "Each chart measures how often stored production score answers agreed with the final human correction recorded in feedback.",
  "The original score answer is the value captured on the feedback record; the human answer is the final corrected value after review.",
  "Buckets are based on when the feedback was edited, not when the call happened and not when the score version was released.",
  "Feedback items marked invalid are excluded before bucketing and rolling-window sampling.",
  `For each bucket, the point first uses feedback edited inside that bucket. If that bucket has fewer than ${rollingMinItems} feedback records, older feedback is added until the sample reaches ${rollingMinItems} records or no earlier feedback exists.`,
  "Lookback records are only used to stabilize sparse buckets; each point still ends at that bucket's end date.",
  "This is not a replay or backtest of historical champion versions. It uses the answers already stored on feedback records.",
];

const AlignmentTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const point = payload[0]?.payload as AlignmentPoint | undefined;
  if (!point) {
    return null;
  }

  const sampleCount = getSampleCount(point);
  const bucketCount = point.bucket_item_count ?? point.item_count;
  const lookbackCount = point.lookback_item_count ?? 0;

  return (
    <div className="rounded-md border bg-background p-3 shadow-lg text-xs space-y-1">
      <div className="font-medium">{point.label}</div>
      <div className="text-muted-foreground">{formatDateRange(point.start, point.end)}</div>
      <div>AC1: {formatValue(point.ac1, 3)}</div>
      <div>Accuracy: {formatValue(point.accuracy, 1)}%</div>
      <div>Sample count: {sampleCount}</div>
      <div>Bucket count: {bucketCount}</div>
      <div>Lookback count: {lookbackCount}</div>
      <div>Sample range: {formatDateRange(point.sample_start, point.sample_end)}</div>
      <div>Agreements: {point.agreements}</div>
      <div>Mismatches: {point.mismatches}</div>
    </div>
  );
};

interface SeriesTimelineChartProps {
  series: AlignmentSeries;
  isOverall?: boolean;
}

const SeriesTimelineChart: React.FC<SeriesTimelineChartProps> = ({ series, isOverall = false }) => {
  const chartData = React.useMemo(() => series.points || [], [series.points]);
  const renderableAc1Points = React.useMemo(
    () => chartData.filter((point) => point.ac1 !== null && point.ac1 !== undefined),
    [chartData]
  );
  const sampleCounts = React.useMemo(
    () => chartData.map(getSampleCount).filter((count) => Number.isFinite(count) && count > 0),
    [chartData]
  );
  const itemCountRange = React.useMemo(() => {
    if (sampleCounts.length === 0) {
      return { min: 0, max: 0 };
    }
    return { min: Math.min(...sampleCounts), max: Math.max(...sampleCounts) };
  }, [sampleCounts]);
  const ac1YAxisFloor = React.useMemo(
    () => (renderableAc1Points.some((point) => (point.ac1 ?? 0) < 0) ? AC1_MIN : 0),
    [renderableAc1Points]
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
  const anyLookback = React.useMemo(
    () => chartData.some((point) => Boolean(point.sample_extended)),
    [chartData]
  );
  const hasRenderableAc1Points = renderableAc1Points.length > 0;
  const canDrawConnectingLine = renderableAc1Points.length > 1;

  const getDotRadius = React.useCallback(
    (point: AlignmentPoint): number => {
      const itemCount = getSampleCount(point);
      if (!Number.isFinite(itemCount) || itemCount <= 0) {
        return 0;
      }
      if (itemCountRange.max <= itemCountRange.min) {
        return 5;
      }
      const normalized = (itemCount - itemCountRange.min) / (itemCountRange.max - itemCountRange.min);
      return 3 + normalized * 6;
    },
    [itemCountRange.max, itemCountRange.min]
  );

  const renderAc1Dot = React.useCallback(
    (dotProps: any) => {
      const point = dotProps?.payload as AlignmentPoint | undefined;
      const dotKey = `ac1-dot-${series.score_id}-${point?.bucket_index ?? "na"}-${dotProps?.index ?? "na"}`;
      const hiddenDot = <circle key={dotKey} cx={0} cy={0} r={0} fill="transparent" stroke="none" />;
      if (!point || point.ac1 === null || point.ac1 === undefined) {
        return hiddenDot;
      }
      const cx = Number(dotProps?.cx);
      const cy = Number(dotProps?.cy);
      if (!Number.isFinite(cx) || !Number.isFinite(cy)) {
        return hiddenDot;
      }
      const radius = getDotRadius(point);
      if (radius <= 0) {
        return hiddenDot;
      }
      return (
        <circle
          key={dotKey}
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
    [getDotRadius, series.score_id]
  );

  const renderActiveAc1Dot = React.useCallback(
    (dotProps: any) => {
      const point = dotProps?.payload as AlignmentPoint | undefined;
      const dotKey = `ac1-active-dot-${series.score_id}-${point?.bucket_index ?? "na"}-${dotProps?.index ?? "na"}`;
      const hiddenDot = <circle key={dotKey} cx={0} cy={0} r={0} fill="transparent" stroke="none" />;
      if (!point || point.ac1 === null || point.ac1 === undefined) {
        return hiddenDot;
      }
      const cx = Number(dotProps?.cx);
      const cy = Number(dotProps?.cy);
      if (!Number.isFinite(cx) || !Number.isFinite(cy)) {
        return hiddenDot;
      }
      return (
        <circle
          key={dotKey}
          cx={cx}
          cy={cy}
          r={getDotRadius(point) + 1.5}
          fill={AC1_COLOR}
          fillOpacity={1}
          stroke="hsl(var(--background))"
          strokeWidth={2}
        />
      );
    },
    [getDotRadius, series.score_id]
  );

  const sampleCopy =
    sampleCounts.length > 0
      ? itemCountRange.min === itemCountRange.max
        ? `${itemCountRange.min} sampled item${itemCountRange.min === 1 ? "" : "s"}`
        : `${itemCountRange.min}-${itemCountRange.max} sampled items`
      : "No sampled items";

  return (
    <section className="rounded-md border bg-background p-3">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h4 className="text-sm font-medium">{isOverall ? "Overall" : series.score_name}</h4>
          {!isOverall && <div className="text-xs text-muted-foreground">{series.score_id}</div>}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{chartData.length} buckets</span>
          <span>{sampleCopy}</span>
          <span>{anyLookback ? "Lookback used" : "No lookback"}</span>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="rounded-md bg-muted/20 p-4 text-sm text-muted-foreground">
          No bucketed alignment data available for this series.
        </div>
      ) : !hasRenderableAc1Points ? (
        <div className="rounded-md bg-muted/20 p-4 text-sm text-muted-foreground">
          No AC1 data is available for this series in the selected buckets.
        </div>
      ) : (
        <>
          <ChartContainer config={chartConfig} className="h-[300px] w-full">
            <LineChart data={chartData} margin={{ top: 12, right: 20, left: 0, bottom: 10 }}>
              {ac1BackgroundBands.map((band, index) => (
                <ReferenceArea
                  key={`ac1-band-${series.score_id}-${index}`}
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
                domain={[ac1YAxisFloor, AC1_MAX]}
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
            Dot size indicates the number of feedback items in each rolling sample.
          </p>
        </>
      )}
    </section>
  );
};

const FeedbackAlignmentTimeline: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<FeedbackAlignmentTimelineData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);
  const isProcessing = Boolean((props.config as any)?.isProcessing);

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
    setLoadedOutput(null);
    setAttachmentLoadError(null);
  }, [props.id, parsedOutput.output_attachment]);

  React.useEffect(() => {
    if (!parsedOutput.output_compacted || !parsedOutput.output_attachment) {
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
  }, [props.id, parsedOutput.output_attachment, parsedOutput.output_compacted]);

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
  const seriesToRender = React.useMemo(
    () => [
      ...(data.overall ? [{ series: data.overall, isOverall: true }] : []),
      ...scores.map((score) => ({ series: score, isOverall: false })),
    ],
    [data.overall, scores]
  );

  const hasChartData = seriesToRender.some(({ series }) => Array.isArray(series.points) && series.points.length > 0);
  const hasResolvedData =
    hasChartData ||
    Boolean(data.message) ||
    Boolean(data.error) ||
    Boolean(data.warning);
  const bucketModeCopy =
    data.bucket_policy?.window_mode === "exact_window"
      ? "exact-window coverage"
      : "complete periods only";
  const rollingMinItems = data.sample_policy?.rolling_min_items ?? DEFAULT_ROLLING_MIN_ITEMS;
  const showMethodology = data.show_methodology !== false;

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
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
          <div>
            <strong className="text-foreground">Mode:</strong>{" "}
            {data.mode === "single_score" ? "Single score" : "All scores on scorecard"}
          </div>
          <div>
            <strong className="text-foreground">Buckets:</strong>{" "}
            {isLoadingCompactedOutput ? "loading..." : data.bucket_policy?.bucket_count ?? 0} x{" "}
            {data.bucket_policy?.bucket_type || "trailing_7d"} ({bucketModeCopy})
          </div>
        </div>

        {typeof data.ignored_invalid_feedback_items === "number" && (
          <div className="text-xs text-muted-foreground">
            Ignored invalid feedback items: {data.ignored_invalid_feedback_items}
            {typeof data.fetched_feedback_items === "number" && (
              <span> of {data.fetched_feedback_items} fetched</span>
            )}
          </div>
        )}

        {showMethodology && (
          <div className="rounded-md border bg-muted/20 p-4 text-sm">
            <div className="font-medium text-foreground">What these charts measure</div>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
              {getMethodologyItems(rollingMinItems).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {data.message && <p className="text-xs text-muted-foreground">{data.message}</p>}

        {isLoadingCompactedOutput ? (
          <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
            Loading bucketed alignment data...
          </div>
        ) : isProcessing && !hasResolvedData ? (
          <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
            Report block is processing. Timeline data will appear when computation completes.
          </div>
        ) : attachmentLoadError ? (
          <div className="rounded-md border bg-amber-50 p-4 text-sm text-amber-800">
            Failed to load attached report data: {attachmentLoadError}
          </div>
        ) : !hasChartData ? (
          <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
            No bucketed alignment data available for the selected series.
          </div>
        ) : (
          <div className="space-y-4">
            {seriesToRender.map(({ series, isOverall }) => (
              <SeriesTimelineChart
                key={`${isOverall ? "overall" : "score"}-${series.score_id}`}
                series={series}
                isOverall={isOverall}
              />
            ))}
          </div>
        )}
      </div>
    </ReportBlock>
  );
};

(FeedbackAlignmentTimeline as BlockComponent).blockClass = "FeedbackAlignmentTimeline";

export default FeedbackAlignmentTimeline;

"use client"

import React, { useState, useMemo, useCallback } from "react"
import { ChartContainer } from "@/components/ui/chart"
import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts"
import { Button } from "@/components/ui/button"
import { TrendingUp, X } from "lucide-react"
import type { ChartConfig } from "@/components/ui/chart"

interface IterationMetrics {
  alignment: number
  accuracy: number
  precision: number
  recall: number
}

export interface IterationData {
  iteration: number
  label?: string
  score_version_id?: string
  feedback_metrics?: IterationMetrics
  accuracy_metrics?: IterationMetrics
  feedback_deltas?: IterationMetrics
  accuracy_deltas?: IterationMetrics
  accepted?: boolean
  skip_reason?: string
  disqualified?: boolean
}

interface OptimizerMetricsChartProps {
  iterations: IterationData[]
}

type DatasetView = "feedback" | "accuracy" | "overall"

// Two dataset colors — shape encodes metric type, color encodes dataset
const FEEDBACK_COLOR    = "var(--chart-1)"
const REGRESSION_COLOR  = "var(--chart-2)"

function getLineColor(key: string, view: DatasetView): string {
  if (key.startsWith("overall_fb"))  return FEEDBACK_COLOR
  if (key.startsWith("overall_acc")) return REGRESSION_COLOR
  return view === "accuracy" ? REGRESSION_COLOR : FEEDBACK_COLOR
}

// chartConfig: labels only — colors are resolved dynamically via getLineColor
const chartConfig: ChartConfig = {
  alignment:             { label: "Alignment",            color: FEEDBACK_COLOR },
  accuracy:              { label: "Accuracy",             color: FEEDBACK_COLOR },
  precision:             { label: "Precision",            color: FEEDBACK_COLOR },
  recall:                { label: "Recall",               color: FEEDBACK_COLOR },
  overall_fb_alignment:  { label: "Feedback Alignment",   color: FEEDBACK_COLOR },
  overall_fb_accuracy:   { label: "Feedback Accuracy",    color: FEEDBACK_COLOR },
  overall_acc_alignment: { label: "Regression Alignment", color: REGRESSION_COLOR },
  overall_acc_accuracy:  { label: "Regression Accuracy",  color: REGRESSION_COLOR },
}

interface ChartDataPoint {
  cycle: string
  accepted?: boolean
  skipped?: boolean
  alignment:  number | null
  accuracy:   number | null
  precision:  number | null
  recall:     number | null
  overall_fb_alignment:  number | null
  overall_fb_accuracy:   number | null
  overall_acc_alignment: number | null
  overall_acc_accuracy:  number | null
}

// Shape encodes metric type — consistent across all views and both datasets
type ShapeKind = "circle" | "square" | "triangle" | "diamond"
const METRIC_SHAPE: Record<string, ShapeKind> = {
  alignment:             "circle",
  accuracy:              "square",
  precision:             "triangle",
  recall:                "diamond",
  overall_fb_alignment:  "circle",
  overall_fb_accuracy:   "square",
  overall_acc_alignment: "circle",   // same shape as alignment — color distinguishes dataset
  overall_acc_accuracy:  "square",   // same shape as accuracy  — color distinguishes dataset
}

// Metric → axis mapping
const METRIC_AXIS: Record<string, "left" | "right"> = {
  alignment: "left", accuracy: "right", precision: "right", recall: "right",
  overall_fb_alignment: "left", overall_fb_accuracy: "right",
  overall_acc_alignment: "left", overall_acc_accuracy: "right",
}

// Which metrics are visible per view
const VIEW_METRICS: Record<DatasetView, string[]> = {
  feedback: ["alignment", "accuracy", "precision", "recall"],
  accuracy: ["alignment", "accuracy", "precision", "recall"],
  overall:  ["overall_fb_alignment", "overall_fb_accuracy", "overall_acc_alignment", "overall_acc_accuracy"],
}

// --- Custom dot shapes for colorblind accessibility ---
const CircleDot = (props: any) => {
  const { cx, cy, fill } = props
  if (cx == null || cy == null) return null
  return <circle cx={cx} cy={cy} r={4} fill={fill} stroke="none" />
}
const SquareDot = (props: any) => {
  const { cx, cy, fill } = props
  if (cx == null || cy == null) return null
  return <rect x={cx - 4} y={cy - 4} width={8} height={8} fill={fill} stroke="none" />
}
const TriangleDot = (props: any) => {
  const { cx, cy, fill } = props
  if (cx == null || cy == null) return null
  return <polygon points={`${cx},${cy - 5} ${cx - 4.5},${cy + 3} ${cx + 4.5},${cy + 3}`} fill={fill} stroke="none" />
}
const DiamondDot = (props: any) => {
  const { cx, cy, fill } = props
  if (cx == null || cy == null) return null
  return <polygon points={`${cx},${cy - 5} ${cx + 4.5},${cy} ${cx},${cy + 5} ${cx - 4.5},${cy}`} fill={fill} stroke="none" />
}

const DOT_COMPONENTS: Record<ShapeKind, React.FC<any>> = {
  circle: CircleDot, square: SquareDot, triangle: TriangleDot, diamond: DiamondDot,
}

// Small inline SVG shapes for legend and tooltip icons
function ShapeIcon({ shape, color, size = 10 }: { shape: ShapeKind; color: string; size?: number }) {
  const s = size
  const h = s / 2
  switch (shape) {
    case "circle":   return <svg width={s} height={s}><circle cx={h} cy={h} r={h - 1} fill={color} /></svg>
    case "square":   return <svg width={s} height={s}><rect x={1} y={1} width={s - 2} height={s - 2} fill={color} /></svg>
    case "triangle":  return <svg width={s} height={s}><polygon points={`${h},1 ${s - 0.5},${s - 1} 0.5,${s - 1}`} fill={color} /></svg>
    case "diamond":  return <svg width={s} height={s}><polygon points={`${h},0 ${s},${h} ${h},${s} 0,${h}`} fill={color} /></svg>
  }
}

// --- Baseline helpers ---
interface BaselineValues {
  alignment: number | null
  accuracy: number | null
  precision: number | null
  recall: number | null
  overall_fb_alignment: number | null
  overall_fb_accuracy: number | null
  overall_acc_alignment: number | null
  overall_acc_accuracy: number | null
}

function extractBaseline(iterations: IterationData[]): BaselineValues {
  const b = iterations.find(it => it.iteration === 0)
  const fm = b?.feedback_metrics
  const am = b?.accuracy_metrics
  return {
    alignment: fm?.alignment ?? null,
    accuracy: fm?.accuracy ?? null,
    precision: fm?.precision ?? null,
    recall: fm?.recall ?? null,
    overall_fb_alignment: fm?.alignment ?? null,
    overall_fb_accuracy: fm?.accuracy ?? null,
    overall_acc_alignment: am?.alignment ?? null,
    overall_acc_accuracy: am?.accuracy ?? null,
  }
}

function formatDelta(val: number | null, base: number | null, isPct: boolean): string | null {
  if (val == null || base == null) return null
  const d = val - base
  const sign = d >= 0 ? "+" : ""
  return isPct ? `${sign}${d.toFixed(1)}%` : `${sign}${d.toFixed(4)}`
}

// --- Tooltip ---
interface MetricsTooltipProps {
  active?: boolean
  payload?: any[]
  datasetView: DatasetView
  baseline: BaselineValues
  focusedMetric: string | null
}

const MetricsTooltip: React.FC<MetricsTooltipProps> = ({ active, payload, datasetView, baseline, focusedMetric }) => {
  if (!active || !payload || payload.length === 0) return null
  const point = payload[0]?.payload as ChartDataPoint | undefined
  if (!point) return null

  const status = point.skipped ? "Skipped" : point.accepted ? "Accepted" : "Rejected"
  const statusColor = point.skipped ? "text-muted-foreground" : point.accepted ? "text-green-600" : "text-red-600"

  const metrics = VIEW_METRICS[datasetView]
  const isBaseline = point.cycle === "Baseline"

  return (
    <div className="rounded-md border bg-background p-3 shadow-lg text-xs space-y-1">
      <div className="font-medium flex items-center justify-between gap-4">
        <span>{point.cycle}</span>
        <span className={statusColor}>{status}</span>
      </div>
      <div className="space-y-0.5 pt-1">
        {metrics.map(key => {
          if (focusedMetric && key !== focusedMetric) return null
          const val = (point as any)[key] as number | null
          const baseVal = (baseline as any)[key] as number | null
          const isPct = METRIC_AXIS[key] === "right"
          const shape = METRIC_SHAPE[key]
          const label = chartConfig[key]?.label || key
          const color = getLineColor(key, datasetView)

          const formatted = val !== null
            ? (isPct ? `${val.toFixed(1)}%` : val.toFixed(4))
            : "N/A"
          const delta = !isBaseline ? formatDelta(val, baseVal, isPct) : null

          return (
            <div key={key} className="flex items-center gap-2">
              <ShapeIcon shape={shape} color={color} />
              <span>
                {label}: {formatted}
                {delta && (
                  <span className={delta.startsWith("+") ? "text-green-500 ml-1" : "text-red-500 ml-1"}>
                    ({delta})
                  </span>
                )}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// --- Custom Legend with click-to-focus and correct shapes ---
interface CustomLegendProps {
  datasetView: DatasetView
  focusedMetric: string | null
  onClickMetric: (dataKey: string) => void
}

const CustomLegend: React.FC<CustomLegendProps> = ({ datasetView, focusedMetric, onClickMetric }) => {
  const metrics = VIEW_METRICS[datasetView]
  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 pt-2" style={{ fontSize: 11 }}>
      {metrics.map(key => {
        const shape = METRIC_SHAPE[key]
        const label = (chartConfig as Record<string, { label: string }>)[key]?.label || key
        const color = getLineColor(key, datasetView)
        const dimmed = focusedMetric !== null && focusedMetric !== key
        return (
          <button
            key={key}
            type="button"
            className="flex items-center gap-1.5 cursor-pointer hover:underline"
            style={{ opacity: dimmed ? 0.3 : 1, transition: "opacity 150ms" }}
            onClick={() => onClickMetric(key)}
          >
            <ShapeIcon shape={shape} color={color} />
            <span style={{ textDecoration: focusedMetric === key ? "underline" : "none" }}>{label}</span>
          </button>
        )
      })}
      {focusedMetric && (
        <button
          type="button"
          className="flex items-center gap-1 text-muted-foreground hover:text-foreground cursor-pointer ml-2 transition-colors"
          onClick={() => onClickMetric(focusedMetric)}
        >
          <X className="h-3 w-3" />
          <span>Show all</span>
        </button>
      )}
    </div>
  )
}

// === Main Component ===
export default function OptimizerMetricsChart({ iterations }: OptimizerMetricsChartProps) {
  const [datasetView, setDatasetView] = useState<DatasetView>("overall")
  const [focusedMetric, setFocusedMetric] = useState<string | null>(null)

  const hasAccuracyData = useMemo(() => iterations.some(it => it.accuracy_metrics), [iterations])

  const baseline = useMemo(() => extractBaseline(iterations), [iterations])

  const chartData = useMemo<ChartDataPoint[]>(() => {
    const points: ChartDataPoint[] = []
    for (const it of iterations) {
      const fm = it.feedback_metrics
      const am = it.accuracy_metrics

      if (datasetView === "feedback" && !fm && !it.skip_reason) continue
      if (datasetView === "accuracy" && !am && !it.skip_reason) continue
      if (datasetView === "overall" && !fm && !am && !it.skip_reason) continue

      const src = datasetView === "accuracy" ? am : fm
      const m = src || { alignment: 0, accuracy: 0, precision: 0, recall: 0 }

      points.push({
        cycle: it.label || `Cycle ${it.iteration}`,
        accepted: it.accepted,
        skipped: Boolean(it.skip_reason),
        alignment:  src ? m.alignment : null,
        accuracy:   src ? m.accuracy  : null,
        precision:  src ? m.precision : null,
        recall:     src ? m.recall    : null,
        overall_fb_alignment:  fm ? fm.alignment : null,
        overall_fb_accuracy:   fm ? fm.accuracy  : null,
        overall_acc_alignment: am ? am.alignment : null,
        overall_acc_accuracy:  am ? am.accuracy  : null,
      })
    }
    return points
  }, [iterations, datasetView])

  const handleDatasetToggle = useCallback((view: DatasetView) => {
    setDatasetView(view)
    setFocusedMetric(null)
  }, [])

  const handleLegendClick = useCallback((dataKey: string) => {
    setFocusedMetric(prev => prev === dataKey ? null : dataKey)
  }, [])

  if (chartData.length === 0) return null

  const visibleMetrics = VIEW_METRICS[datasetView]

  const isVisible = (key: string) => {
    if (!visibleMetrics.includes(key)) return false
    if (focusedMetric && key !== focusedMetric) return false
    return true
  }

  const renderTooltip = (props: any) => (
    <MetricsTooltip {...props} datasetView={datasetView} baseline={baseline} focusedMetric={focusedMetric} />
  )

  const referenceLines = visibleMetrics
    .filter(key => isVisible(key) && (baseline as any)[key] != null)
    .map(key => (
      <ReferenceLine
        key={`baseline-${key}`}
        yAxisId={METRIC_AXIS[key]}
        y={(baseline as any)[key]}
        stroke={getLineColor(key, datasetView)}
        strokeOpacity={0.35}
        strokeDasharray="6 4"
        strokeWidth={1.5}
      />
    ))

  // All 8 line definitions — shape derives from METRIC_SHAPE, color from getLineColor
  const ALL_LINES: Array<{ key: string; axis: "left" | "right" }> = [
    { key: "alignment",             axis: "left"  },
    { key: "accuracy",              axis: "right" },
    { key: "precision",             axis: "right" },
    { key: "recall",                axis: "right" },
    { key: "overall_fb_alignment",  axis: "left"  },
    { key: "overall_fb_accuracy",   axis: "right" },
    { key: "overall_acc_alignment", axis: "left"  },
    { key: "overall_acc_accuracy",  axis: "right" },
  ]

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-muted-foreground">Optimizer Metrics</span>
        </div>
        {hasAccuracyData && (
          <div className="flex gap-1">
            {(["overall", "feedback", "accuracy"] as DatasetView[]).map(view => (
              <Button
                key={view}
                variant={datasetView === view ? "default" : "ghost"}
                size="sm"
                className="h-5 !text-sm !leading-5 px-2"
                onClick={() => handleDatasetToggle(view)}
              >
                {view.charAt(0).toUpperCase() + view.slice(1)}
              </Button>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-md bg-card p-3">
        <ChartContainer config={chartConfig} className="h-[260px] w-full">
          <LineChart data={chartData} margin={{ top: 8, right: 48, left: 0, bottom: 4 }}>
            <CartesianGrid stroke="hsl(var(--foreground) / 0.12)" strokeDasharray="3 3" />
            <XAxis
              dataKey="cycle"
              tick={{ fill: "hsl(var(--foreground) / 0.7)", fontSize: 10 }}
              axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              interval={0}
            />
            <YAxis
              yAxisId="left"
              domain={[-1, 1]}
              ticks={[-1, -0.5, 0, 0.5, 1]}
              tick={{ fill: "hsl(var(--foreground) / 0.7)", fontSize: 11 }}
              axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tickFormatter={(v: number) => v.toFixed(1)}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={{ fill: "hsl(var(--foreground) / 0.7)", fontSize: 11 }}
              axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tickFormatter={(v: number) => `${v}%`}
            />
            <Tooltip content={renderTooltip} />

            {/* Baseline reference lines (dashed, low opacity) */}
            {referenceLines}

            {/* Data lines — shape = metric type, color = dataset */}
            {ALL_LINES.map(({ key, axis }) => {
              const visible = isVisible(key)
              const shape = METRIC_SHAPE[key]
              const DotComp = DOT_COMPONENTS[shape]
              const color = getLineColor(key, datasetView)
              return (
                <Line
                  key={key}
                  yAxisId={axis}
                  hide={!visible}
                  legendType="none"
                  type="monotone"
                  dataKey={key}
                  name={(chartConfig as Record<string, { label: string }>)[key]?.label || key}
                  stroke={color}
                  strokeWidth={2}
                  dot={<DotComp fill={color} />}
                  activeDot={{ r: 6 }}
                  connectNulls
                  isAnimationActive={false}
                />
              )
            })}
          </LineChart>
        </ChartContainer>

        {/* Custom legend with correct shapes and click-to-focus */}
        <CustomLegend
          datasetView={datasetView}
          focusedMetric={focusedMetric}
          onClickMetric={handleLegendClick}
        />

        {chartData.length === 1 && (
          <p className="mt-1 text-xs text-muted-foreground">
            Only one cycle completed so far.
          </p>
        )}
      </div>
    </div>
  )
}

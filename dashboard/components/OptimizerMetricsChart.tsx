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
  recent_metrics?: IterationMetrics
  regression_metrics?: IterationMetrics
  recent_deltas?: IterationMetrics
  regression_deltas?: IterationMetrics
  recent_cost_per_item?: number | null
  regression_cost_per_item?: number | null
  accepted?: boolean
  skip_reason?: string
  disqualified?: boolean
}

export type DatasetView = "recent" | "regression" | "overall"

interface OptimizerMetricsChartProps {
  iterations: IterationData[]
  datasetView?: DatasetView
  onDatasetViewChange?: (view: DatasetView) => void
}

const RECENT_COLOR = "var(--chart-1)"
const REGRESSION_COLOR = "var(--chart-2)"

function getLineColor(key: string, view: DatasetView): string {
  if (key.startsWith("overall_recent")) return RECENT_COLOR
  if (key.startsWith("overall_regression")) return REGRESSION_COLOR
  return view === "regression" ? REGRESSION_COLOR : RECENT_COLOR
}

const chartConfig: ChartConfig = {
  alignment: { label: "Alignment", color: RECENT_COLOR },
  accuracy: { label: "Accuracy", color: RECENT_COLOR },
  precision: { label: "Precision", color: RECENT_COLOR },
  recall: { label: "Recall", color: RECENT_COLOR },
  overall_recent_alignment: { label: "Recent Alignment", color: RECENT_COLOR },
  overall_recent_accuracy: { label: "Recent Accuracy", color: RECENT_COLOR },
  overall_regression_alignment: { label: "Regression Alignment", color: REGRESSION_COLOR },
  overall_regression_accuracy: { label: "Regression Accuracy", color: REGRESSION_COLOR },
}

interface ChartDataPoint {
  cycle: string
  accepted?: boolean
  skipped?: boolean
  alignment: number | null
  accuracy: number | null
  precision: number | null
  recall: number | null
  overall_recent_alignment: number | null
  overall_recent_accuracy: number | null
  overall_regression_alignment: number | null
  overall_regression_accuracy: number | null
}

type ShapeKind = "circle" | "square" | "triangle" | "diamond"
const METRIC_SHAPE: Record<string, ShapeKind> = {
  alignment: "circle",
  accuracy: "square",
  precision: "triangle",
  recall: "diamond",
  overall_recent_alignment: "circle",
  overall_recent_accuracy: "square",
  overall_regression_alignment: "circle",
  overall_regression_accuracy: "square",
}

const METRIC_AXIS: Record<string, "left" | "right"> = {
  alignment: "left", accuracy: "right", precision: "right", recall: "right",
  overall_recent_alignment: "left", overall_recent_accuracy: "right",
  overall_regression_alignment: "left", overall_regression_accuracy: "right",
}

const VIEW_METRICS: Record<DatasetView, string[]> = {
  recent: ["alignment", "accuracy", "precision", "recall"],
  regression: ["alignment", "accuracy", "precision", "recall"],
  overall: ["overall_recent_alignment", "overall_recent_accuracy", "overall_regression_alignment", "overall_regression_accuracy"],
}

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

function ShapeIcon({ shape, color, size = 10 }: { shape: ShapeKind; color: string; size?: number }) {
  const s = size
  const h = s / 2
  switch (shape) {
    case "circle": return <svg width={s} height={s}><circle cx={h} cy={h} r={h - 1} fill={color} /></svg>
    case "square": return <svg width={s} height={s}><rect x={1} y={1} width={s - 2} height={s - 2} fill={color} /></svg>
    case "triangle": return <svg width={s} height={s}><polygon points={`${h},1 ${s - 0.5},${s - 1} 0.5,${s - 1}`} fill={color} /></svg>
    case "diamond": return <svg width={s} height={s}><polygon points={`${h},0 ${s},${h} ${h},${s} 0,${h}`} fill={color} /></svg>
  }
}

interface AxisTickProps {
  x?: number
  y?: number
  payload?: { value: number }
}

const LeftAxisTick: React.FC<AxisTickProps> = ({ x = 0, y = 0, payload }) => {
  const value = payload?.value
  if (typeof value !== "number") return null

  return (
    <text x={x - 8} y={y} textAnchor="end" fill="hsl(var(--foreground) / 0.7)" fontSize={11}>
      <tspan x={x - 8} dy="0.35em">{value.toFixed(1)}</tspan>
      {value === -1 && <tspan x={x - 8} dy="1.2em" fontSize={10}>AC1</tspan>}
    </text>
  )
}

const RightAxisTick: React.FC<AxisTickProps> = ({ x = 0, y = 0, payload }) => {
  const value = payload?.value
  if (typeof value !== "number") return null

  return (
    <text x={x + 8} y={y} textAnchor="start" fill="hsl(var(--foreground) / 0.7)" fontSize={11}>
      <tspan x={x + 8} dy="0.35em">{value}%</tspan>
      {value === 0 && <tspan x={x + 8} dy="1.2em" fontSize={10}>Acc</tspan>}
    </text>
  )
}

interface BaselineValues {
  alignment: number | null
  accuracy: number | null
  precision: number | null
  recall: number | null
  overall_recent_alignment: number | null
  overall_recent_accuracy: number | null
  overall_regression_alignment: number | null
  overall_regression_accuracy: number | null
}

function extractBaseline(iterations: IterationData[]): BaselineValues {
  const b = iterations.find(it => it.iteration === 0)
  const recentMetrics = b?.recent_metrics
  const regressionMetrics = b?.regression_metrics
  return {
    alignment: recentMetrics?.alignment ?? null,
    accuracy: recentMetrics?.accuracy ?? null,
    precision: recentMetrics?.precision ?? null,
    recall: recentMetrics?.recall ?? null,
    overall_recent_alignment: recentMetrics?.alignment ?? null,
    overall_recent_accuracy: recentMetrics?.accuracy ?? null,
    overall_regression_alignment: regressionMetrics?.alignment ?? null,
    overall_regression_accuracy: regressionMetrics?.accuracy ?? null,
  }
}

function formatDelta(val: number | null, base: number | null, isPct: boolean): string | null {
  if (val == null || base == null) return null
  const d = val - base
  const sign = d >= 0 ? "+" : ""
  return isPct ? `${sign}${d.toFixed(1)}%` : `${sign}${d.toFixed(4)}`
}

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

export default function OptimizerMetricsChart({ iterations, datasetView: controlledDatasetView, onDatasetViewChange }: OptimizerMetricsChartProps) {
  const [uncontrolledDatasetView, setUncontrolledDatasetView] = useState<DatasetView>("overall")
  const [focusedMetric, setFocusedMetric] = useState<string | null>(null)

  const datasetView = controlledDatasetView ?? uncontrolledDatasetView
  const hasRegressionData = useMemo(() => iterations.some(it => it.regression_metrics), [iterations])

  const baseline = useMemo(() => extractBaseline(iterations), [iterations])

  const chartData = useMemo<ChartDataPoint[]>(() => {
    const points: ChartDataPoint[] = []
    for (const it of iterations) {
      const recentMetrics = it.recent_metrics
      const regressionMetrics = it.regression_metrics

      if (datasetView === "recent" && !recentMetrics && !it.skip_reason) continue
      if (datasetView === "regression" && !regressionMetrics && !it.skip_reason) continue
      if (datasetView === "overall" && !recentMetrics && !regressionMetrics && !it.skip_reason) continue

      const src = datasetView === "regression" ? regressionMetrics : recentMetrics
      const m = src || { alignment: 0, accuracy: 0, precision: 0, recall: 0 }

      points.push({
        cycle: it.label || `Cycle ${it.iteration}`,
        accepted: it.accepted,
        skipped: Boolean(it.skip_reason),
        alignment: src ? m.alignment : null,
        accuracy: src ? m.accuracy : null,
        precision: src ? m.precision : null,
        recall: src ? m.recall : null,
        overall_recent_alignment: recentMetrics ? recentMetrics.alignment : null,
        overall_recent_accuracy: recentMetrics ? recentMetrics.accuracy : null,
        overall_regression_alignment: regressionMetrics ? regressionMetrics.alignment : null,
        overall_regression_accuracy: regressionMetrics ? regressionMetrics.accuracy : null,
      })
    }
    return points
  }, [iterations, datasetView])

  const handleDatasetToggle = useCallback((view: DatasetView) => {
    if (controlledDatasetView === undefined) {
      setUncontrolledDatasetView(view)
    }
    onDatasetViewChange?.(view)
    setFocusedMetric(null)
  }, [controlledDatasetView, onDatasetViewChange])

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

  const allLines: Array<{ key: string; axis: "left" | "right" }> = [
    { key: "alignment", axis: "left" },
    { key: "accuracy", axis: "right" },
    { key: "precision", axis: "right" },
    { key: "recall", axis: "right" },
    { key: "overall_recent_alignment", axis: "left" },
    { key: "overall_recent_accuracy", axis: "right" },
    { key: "overall_regression_alignment", axis: "left" },
    { key: "overall_regression_accuracy", axis: "right" },
  ]

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-muted-foreground">Optimizer Metrics</span>
        </div>
        {hasRegressionData && (
          <div className="flex gap-1">
            {([
              { value: "overall", label: "Overall" },
              { value: "recent", label: "Recent" },
              { value: "regression", label: "Regression" },
            ] as const).map(view => (
              <Button
                key={view.value}
                variant={datasetView === view.value ? "default" : "ghost"}
                size="sm"
                className="h-5 !text-sm !leading-5 px-2"
                onClick={() => handleDatasetToggle(view.value)}
              >
                {view.label}
              </Button>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-md bg-card p-2">
        <ChartContainer config={chartConfig} className="h-[260px] w-full">
          <LineChart data={chartData} margin={{ top: 8, right: 52, left: 20, bottom: 16 }}>
            <CartesianGrid stroke="hsl(var(--foreground) / 0.12)" strokeDasharray="3 3" />
            <XAxis
              dataKey="cycle"
              tick={{ fill: "hsl(var(--foreground) / 0.7)", fontSize: 10 }}
              axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              interval={0}
              padding={{ left: 28, right: 28 }}
            />
            <YAxis
              yAxisId="left"
              domain={[-1, 1]}
              ticks={[-1, -0.5, 0, 0.5, 1]}
              tick={{ fill: "hsl(var(--foreground) / 0.7)", fontSize: 11 }}
              axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tick={<LeftAxisTick />}
              width={52}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={{ fill: "hsl(var(--foreground) / 0.7)", fontSize: 11 }}
              axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
              tick={<RightAxisTick />}
              width={56}
            />
            <Tooltip content={renderTooltip} />

            {referenceLines}

            {allLines.map(({ key, axis }) => {
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

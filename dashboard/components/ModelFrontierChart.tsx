"use client"

import React, { useMemo } from "react"
import {
  CartesianGrid,
  LabelList,
  ReferenceLine,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts"
import { CircleDollarSign, TrendingUp } from "lucide-react"
import { ChartContainer } from "@/components/ui/chart"
import type { ChartConfig } from "@/components/ui/chart"

export interface ModelFrontierRow {
  label?: string | null
  model_provider?: string | null
  model_name?: string | null
  base_model_name?: string | null
  reasoning_effort?: string | null
  verbosity?: string | null
  temperature?: number | null
  max_tokens?: number | null
  score_version_id?: string | null
  feedback_evaluation_id?: string | null
  regression_evaluation_id?: string | null
  cost_axis?: number | null
  accuracy_axis?: number | null
  total_cost?: number | null
  processed_items?: number | null
  is_current?: boolean | null
  is_pareto_frontier?: boolean | null
  status?: string | null
  error?: string | null
}

interface ModelFrontierChartProps {
  rows: ModelFrontierRow[]
}

interface FrontierPoint extends ModelFrontierRow {
  x: number
  y: number
  shortLabel: string
  series: "current" | "frontier" | "candidate"
}

const FRONTIER_COLOR = "var(--chart-1)"
const CURRENT_COLOR = "var(--chart-3)"
const CANDIDATE_COLOR = "var(--chart-2)"

const chartConfig: ChartConfig = {
  frontier: { label: "Pareto Frontier", color: FRONTIER_COLOR },
  current: { label: "Current", color: CURRENT_COLOR },
  candidate: { label: "Candidate", color: CANDIDATE_COLOR },
}

function formatCurrency(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A"
  if (value === 0) return "$0.00"
  if (Math.abs(value) < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

function formatNumber(value: number | null | undefined, digits = 4): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "N/A"
  return value.toFixed(digits)
}

function truncateLabel(value: string): string {
  return value.length > 24 ? `${value.slice(0, 21)}...` : value
}

function pointColor(point: FrontierPoint): string {
  if (point.is_current) return CURRENT_COLOR
  if (point.is_pareto_frontier) return FRONTIER_COLOR
  return CANDIDATE_COLOR
}

const FrontierDot = (props: any) => {
  const { cx, cy, payload } = props
  if (cx == null || cy == null || !payload) return null
  const point = payload as FrontierPoint
  const radius = point.is_current ? 6 : point.is_pareto_frontier ? 5.5 : 4.5
  return (
    <circle
      cx={cx}
      cy={cy}
      r={radius}
      fill={pointColor(point)}
      stroke="hsl(var(--background))"
      strokeWidth={1.5}
    />
  )
}

const FrontierTooltip = ({ active, payload }: any) => {
  if (!active || !payload || payload.length === 0) return null
  const point = payload[0]?.payload as FrontierPoint | undefined
  if (!point) return null

  return (
    <div className="max-w-[280px] rounded-md bg-background/95 p-3 text-xs shadow-lg">
      <div className="mb-1 flex items-start justify-between gap-3">
        <span className="font-medium">{point.label || "Variant"}</span>
        <span className="text-muted-foreground">
          {point.is_current ? "Current" : point.is_pareto_frontier ? "Frontier" : "Candidate"}
        </span>
      </div>
      <div className="space-y-0.5 text-muted-foreground">
        <div>Feedback AC1: <span className="text-foreground">{formatNumber(point.accuracy_axis)}</span></div>
        <div>Cost / item: <span className="text-foreground">{formatCurrency(point.cost_axis)}</span></div>
        <div>Total cost: <span className="text-foreground">{formatCurrency(point.total_cost)}</span></div>
        <div>Items: <span className="text-foreground">{point.processed_items ?? "N/A"}</span></div>
        {point.model_name && <div>Model: <span className="text-foreground">{point.model_name}</span></div>}
        {point.reasoning_effort && <div>Reasoning: <span className="text-foreground">{point.reasoning_effort}</span></div>}
        {point.verbosity && <div>Verbosity: <span className="text-foreground">{point.verbosity}</span></div>}
        {point.error && <div className="pt-1 text-destructive">{point.error}</div>}
      </div>
    </div>
  )
}

export default function ModelFrontierChart({ rows }: ModelFrontierChartProps) {
  const points = useMemo<FrontierPoint[]>(() => {
    return rows
      .filter(row =>
        typeof row.cost_axis === "number" &&
        row.cost_axis > 0 &&
        typeof row.accuracy_axis === "number"
      )
      .map(row => ({
        ...row,
        x: row.cost_axis as number,
        y: row.accuracy_axis as number,
        shortLabel: truncateLabel(String(row.label || row.model_name || "Variant")),
        series: (row.is_current ? "current" : row.is_pareto_frontier ? "frontier" : "candidate") as FrontierPoint["series"],
      }))
      .sort((left, right) => left.x - right.x)
  }, [rows])

  const domain = useMemo<[number, number]>(() => {
    if (points.length === 0) return [0.0001, 1]
    const min = Math.min(...points.map(point => point.x))
    const max = Math.max(...points.map(point => point.x))
    if (min === max) return [min / 2, max * 2]
    return [Math.max(min / 2, 0.000001), max * 2]
  }, [points])

  const frontierCount = rows.filter(row => row.is_pareto_frontier).length
  const errorCount = rows.filter(row => row.status === "error" || row.error).length

  if (rows.length === 0) return null

  return (
    <div className="mt-4 rounded-lg bg-card p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-muted-foreground">Model Frontier</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>{rows.length} variants</span>
          <span>{frontierCount} frontier</span>
          {errorCount > 0 && <span className="text-destructive">{errorCount} errors</span>}
        </div>
      </div>

      <div className="rounded-md bg-background p-2">
        {points.length > 0 ? (
          <ChartContainer config={chartConfig} className="h-[300px] w-full">
            <ScatterChart margin={{ top: 18, right: 30, left: 20, bottom: 26 }}>
              <CartesianGrid stroke="hsl(var(--foreground) / 0.12)" strokeDasharray="3 3" />
              <XAxis
                dataKey="x"
                type="number"
                name="Cost per evaluated item"
                scale="log"
                domain={domain}
                tickFormatter={(value) => formatCurrency(Number(value))}
                tick={{ fill: "hsl(var(--foreground) / 0.7)", fontSize: 10 }}
                axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                label={{ value: "Cost per evaluated item (log scale)", position: "insideBottom", offset: -18, fill: "hsl(var(--foreground) / 0.7)", fontSize: 11 }}
              />
              <YAxis
                dataKey="y"
                type="number"
                name="Feedback AC1"
                domain={[-1, 1]}
                ticks={[-1, -0.5, 0, 0.5, 1]}
                tickFormatter={(value) => Number(value).toFixed(1)}
                tick={{ fill: "hsl(var(--foreground) / 0.7)", fontSize: 10 }}
                axisLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                tickLine={{ stroke: "hsl(var(--foreground) / 0.25)" }}
                label={{ value: "Feedback AC1", angle: -90, position: "insideLeft", fill: "hsl(var(--foreground) / 0.7)", fontSize: 11 }}
                width={58}
              />
              <ZAxis range={[80, 80]} />
              <ReferenceLine y={0} stroke="hsl(var(--foreground) / 0.18)" />
              <Tooltip content={<FrontierTooltip />} />
              <Scatter data={points} shape={<FrontierDot />} isAnimationActive={false}>
                <LabelList dataKey="shortLabel" position="top" fill="hsl(var(--foreground) / 0.65)" fontSize={10} />
              </Scatter>
            </ScatterChart>
          </ChartContainer>
        ) : (
          <div className="flex h-[180px] items-center justify-center text-sm text-muted-foreground">
            No completed frontier points yet.
          </div>
        )}

        <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5"><CircleDollarSign className="h-3 w-3" /> Lower cost is better</div>
          <div className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: FRONTIER_COLOR }} /> Pareto frontier</div>
          <div className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: CURRENT_COLOR }} /> Current config</div>
          <div className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: CANDIDATE_COLOR }} /> Candidate</div>
        </div>

        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[640px] text-xs">
            <thead className="text-muted-foreground">
              <tr className="border-b border-border/50">
                <th className="py-1 text-left font-medium">Variant</th>
                <th className="py-1 text-left font-medium">Model</th>
                <th className="py-1 text-right font-medium">Feedback AC1</th>
                <th className="py-1 text-right font-medium">Cost / Item</th>
                <th className="py-1 text-right font-medium">Total Cost</th>
                <th className="py-1 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.label || "variant"}-${index}`} className="border-b border-border/30 last:border-0">
                  <td className="py-1.5 pr-2">
                    <span className="font-medium">{row.label || "Variant"}</span>
                    {row.is_current && <span className="ml-2 text-muted-foreground">current</span>}
                    {row.is_pareto_frontier && <span className="ml-2 text-muted-foreground">frontier</span>}
                  </td>
                  <td className="py-1.5 pr-2 text-muted-foreground">{row.model_name || "N/A"}</td>
                  <td className="py-1.5 text-right tabular-nums">{formatNumber(row.accuracy_axis)}</td>
                  <td className="py-1.5 text-right tabular-nums">{formatCurrency(row.cost_axis)}</td>
                  <td className="py-1.5 text-right tabular-nums">{formatCurrency(row.total_cost)}</td>
                  <td className="py-1.5 pl-2 text-muted-foreground">{row.error ? "error" : row.status || "completed"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

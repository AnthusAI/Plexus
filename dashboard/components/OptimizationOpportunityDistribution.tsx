"use client"

import React, { useMemo, useState } from "react"
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { ChartContainer } from "@/components/ui/chart"
import type { ChartConfig } from "@/components/ui/chart"

export type OptimizationOpportunityDisposition =
  | "selected_for_review"
  | "eligible"
  | "cooldown"
  | "blocked"
  | "incomplete"

export interface OptimizationOpportunityRow {
  evidence_rank: number
  opportunity: number
  disposition: OptimizationOpportunityDisposition
  scorecard_name: string
  score_name: string
  reason?: string | null
  eligibility_timestamp?: string | null
  dashboard_url?: string | null
  disagreement_rate?: number | null
  valid_feedback_count?: number | null
}

interface OptimizationOpportunityDistributionProps {
  rows: OptimizationOpportunityRow[]
}

type OpportunityScale = "linear" | "log"

interface ChartPoint extends OptimizationOpportunityRow {
  chart_opportunity: number
  display_name: string
  marker_radius: number
  disagreement_fraction: number | null
}

const DISPOSITIONS: Record<OptimizationOpportunityDisposition, {
  label: string
  color: string
  shape: "circle" | "square" | "triangle" | "diamond" | "cross"
}> = {
  selected_for_review: {
    label: "Selected for review",
    color: "hsl(var(--chart-1))",
    shape: "circle",
  },
  eligible: {
    label: "Eligible",
    color: "hsl(var(--chart-2))",
    shape: "square",
  },
  cooldown: {
    label: "Cooling down",
    color: "hsl(var(--chart-3))",
    shape: "triangle",
  },
  blocked: {
    label: "Blocked",
    color: "hsl(var(--chart-4))",
    shape: "cross",
  },
  incomplete: {
    label: "Incomplete evidence",
    color: "hsl(var(--chart-5))",
    shape: "diamond",
  },
}

const chartConfig: ChartConfig = Object.fromEntries(
  Object.entries(DISPOSITIONS).map(([key, value]) => [key, { label: value.label, color: value.color }]),
)

function isFiniteNumber(value: number): boolean {
  return Number.isFinite(value)
}

function formatOpportunity(value: number): string {
  if (!isFiniteNumber(value)) return "Not available"
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value)
}

function formatPercentage(value: number | null | undefined): string {
  const fraction = normalizeDisagreementRate(value)
  if (fraction === null) return "Not available"
  return new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 0 }).format(fraction)
}

function formatFeedbackVolume(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return "Not available"
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value)
}

function normalizeDisagreementRate(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return null
  if (value <= 1) return value
  return value <= 100 ? value / 100 : null
}

function markerRadius(value: number | null | undefined, minimum: number | null, maximum: number | null): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || minimum === null || maximum === null) {
    return 5
  }
  if (minimum === maximum) return 8
  const normalized = Math.max(0, Math.min(1, (value - minimum) / (maximum - minimum)))
  return 5 + Math.sqrt(normalized) * 5
}

function formatTimestamp(value: string | null | undefined): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
}

function displayName(row: OptimizationOpportunityRow): string {
  const scorecard = row.scorecard_name.trim() || "Unnamed scorecard"
  const score = row.score_name.trim() || "Unnamed score"
  return `${scorecard} — ${score}`
}

function DispositionMark({ cx, cy, payload }: { cx?: number; cy?: number; payload?: ChartPoint }) {
  if (cx == null || cy == null || !payload) return null
  const disposition = DISPOSITIONS[payload.disposition]
  const { color, shape } = disposition
  const radius = payload.marker_radius
  const disagreementRadius = payload.disagreement_fraction === null
    ? 0
    : Math.max(1.2, radius * payload.disagreement_fraction)
  const common = { fill: color, stroke: "hsl(var(--background))", strokeWidth: 1.5 }
  const innerFill = disagreementRadius > 0
    ? <circle cx={cx} cy={cy} r={disagreementRadius} fill="hsl(var(--foreground))" fillOpacity={0.72} />
    : null

  switch (shape) {
    case "square":
      return <g><rect x={cx - radius} y={cy - radius} width={radius * 2} height={radius * 2} rx={1} {...common} />{innerFill}</g>
    case "triangle":
      return <g><path d={`M ${cx} ${cy - radius} L ${cx + radius} ${cy + radius * 0.82} L ${cx - radius} ${cy + radius * 0.82} Z`} {...common} />{innerFill}</g>
    case "diamond":
      return <g><path d={`M ${cx} ${cy - radius} L ${cx + radius} ${cy} L ${cx} ${cy + radius} L ${cx - radius} ${cy} Z`} {...common} />{innerFill}</g>
    case "cross":
      return (
        <g>
          <path
            d={`M ${cx - radius} ${cy - radius} L ${cx + radius} ${cy + radius} M ${cx + radius} ${cy - radius} L ${cx - radius} ${cy + radius}`}
            fill="none"
            stroke={color}
            strokeWidth={2.5}
            strokeLinecap="round"
          />
          {innerFill}
        </g>
      )
    default:
      return <g><circle cx={cx} cy={cy} r={radius} {...common} />{innerFill}</g>
  }
}

function OpportunityTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload?: ChartPoint }> }) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  const disposition = DISPOSITIONS[point.disposition]
  const eligibleAt = formatTimestamp(point.eligibility_timestamp)

  return (
    <div className="max-w-[320px] rounded-md bg-background/95 p-3 text-xs shadow-lg">
      <p className="font-medium text-foreground">{point.display_name}</p>
      <dl className="mt-1 space-y-0.5 text-muted-foreground">
        <div><dt className="inline">Evidence rank: </dt><dd className="inline text-foreground">{point.evidence_rank}</dd></div>
        <div><dt className="inline">Reviewed-error opportunity: </dt><dd className="inline text-foreground">{formatOpportunity(point.opportunity)}</dd></div>
        <div><dt className="inline">Disagreement rate: </dt><dd className="inline text-foreground">{formatPercentage(point.disagreement_rate)}</dd></div>
        <div><dt className="inline">Valid feedback: </dt><dd className="inline text-foreground">{formatFeedbackVolume(point.valid_feedback_count)}</dd></div>
        <div><dt className="inline">Disposition: </dt><dd className="inline text-foreground">{disposition.label}</dd></div>
        {point.reason && <div><dt className="inline">Reason: </dt><dd className="inline text-foreground">{point.reason}</dd></div>}
        {eligibleAt && <div><dt className="inline">Eligible after: </dt><dd className="inline text-foreground">{eligibleAt}</dd></div>}
      </dl>
    </div>
  )
}

export default function OptimizationOpportunityDistribution({ rows }: OptimizationOpportunityDistributionProps) {
  const [scale, setScale] = useState<OpportunityScale>("linear")
  const sortedRows = useMemo(
    () => rows
      .filter(row => isFiniteNumber(row.evidence_rank) && isFiniteNumber(row.opportunity))
      .slice()
      .sort((left, right) => left.evidence_rank - right.evidence_rank),
    [rows],
  )
  const smallestPositiveOpportunity = useMemo(() => {
    const positives = sortedRows.map(row => row.opportunity).filter(value => value > 0)
    return positives.length > 0 ? Math.min(...positives) : 1
  }, [sortedRows])
  const containsZeroOrNegative = sortedRows.some(row => row.opportunity <= 0)
  const feedbackVolumeBounds = useMemo(() => {
    const values = sortedRows
      .map(row => row.valid_feedback_count)
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0)
    return values.length > 0
      ? { minimum: Math.min(...values), maximum: Math.max(...values) }
      : { minimum: null, maximum: null }
  }, [sortedRows])
  const points = useMemo<ChartPoint[]>(() => sortedRows.map(row => ({
    ...row,
    chart_opportunity: scale === "log" && row.opportunity <= 0
      ? smallestPositiveOpportunity / 10
      : row.opportunity,
    display_name: displayName(row),
    marker_radius: markerRadius(
      row.valid_feedback_count,
      feedbackVolumeBounds.minimum,
      feedbackVolumeBounds.maximum,
    ),
    disagreement_fraction: normalizeDisagreementRate(row.disagreement_rate),
  })), [feedbackVolumeBounds.maximum, feedbackVolumeBounds.minimum, scale, smallestPositiveOpportunity, sortedRows])
  const dispositionCounts = useMemo(() => Object.fromEntries(
    Object.keys(DISPOSITIONS).map(disposition => [
      disposition,
      points.filter(point => point.disposition === disposition).length,
    ]),
  ) as Record<OptimizationOpportunityDisposition, number>, [points])
  const opportunityMax = Math.max(...points.map(point => point.chart_opportunity), 0)

  if (rows.length === 0) return null

  return (
    <section className="mt-4 rounded-lg bg-card p-4" aria-labelledby="optimization-opportunity-distribution-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 id="optimization-opportunity-distribution-title" className="text-sm font-medium">
            Opportunity distribution
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Every evidence-ranked score is shown. A sharp fall indicates a small number of dominant priorities; a smooth curve indicates work is spread across the portfolio.
          </p>
        </div>
        <div className="flex items-center gap-1" role="group" aria-label="Opportunity scale">
          <span className="mr-1 text-xs text-muted-foreground">View:</span>
          {(["linear", "log"] as OpportunityScale[]).map(value => (
            <button
              key={value}
              type="button"
              aria-pressed={scale === value}
              onClick={() => setScale(value)}
              className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                scale === value
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
              }`}
            >
              {value === "linear" ? "Linear" : "Log"}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Disposition legend">
        {Object.entries(DISPOSITIONS).map(([key, value]) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: value.color }} aria-hidden="true" />
            {value.label} ({dispositionCounts[key as OptimizationOpportunityDisposition]})
          </span>
        ))}
      </div>

      <p className="mt-2 text-xs text-muted-foreground" aria-label="Feedback signal legend">
        Point size represents valid feedback volume; larger markers indicate more reviewed feedback. Inner fill represents disagreement rate; a larger inner fill indicates more reviewer disagreement.
      </p>

      <div className="mt-3 rounded-md bg-background p-2">
        {points.length > 0 ? (
          <ChartContainer config={chartConfig} className="h-[300px] w-full">
            <ComposedChart data={points} margin={{ top: 16, right: 24, left: 18, bottom: 30 }}>
              <CartesianGrid stroke="hsl(var(--foreground) / 0.12)" strokeDasharray="3 3" />
              <XAxis
                dataKey="evidence_rank"
                type="number"
                domain={[1, "dataMax"]}
                allowDecimals={false}
                name="Evidence rank"
                label={{ value: "Evidence rank (highest opportunity first)", position: "insideBottom", offset: -18, fill: "hsl(var(--foreground) / 0.7)", fontSize: 11 }}
              />
              <YAxis
                dataKey="chart_opportunity"
                type="number"
                scale={scale}
                domain={scale === "log" ? [Math.max(smallestPositiveOpportunity / 10, Number.MIN_VALUE), "auto"] : [0, Math.max(opportunityMax * 1.05, 1)]}
                tickFormatter={(value) => formatOpportunity(Number(value))}
                name="Reviewed-error opportunity"
                label={{ value: `Reviewed-error opportunity (${scale} scale)`, angle: -90, position: "insideLeft", fill: "hsl(var(--foreground) / 0.7)", fontSize: 11 }}
                width={70}
              />
              <Tooltip content={<OpportunityTooltip />} />
              <Legend wrapperStyle={{ fontSize: 0, height: 0, overflow: "hidden" }} />
              <Line
                type="monotone"
                dataKey="chart_opportunity"
                stroke="hsl(var(--foreground) / 0.45)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="All evidence-ranked scores"
              />
              {(Object.keys(DISPOSITIONS) as OptimizationOpportunityDisposition[]).map(disposition => (
                <Scatter
                  key={disposition}
                  data={points.filter(point => point.disposition === disposition)}
                  dataKey="chart_opportunity"
                  name={DISPOSITIONS[disposition].label}
                  shape={<DispositionMark />}
                  isAnimationActive={false}
                />
              ))}
            </ComposedChart>
          </ChartContainer>
        ) : (
          <p className="flex h-[180px] items-center justify-center text-sm text-muted-foreground">
            No numeric opportunity rows are available for this report.
          </p>
        )}
      </div>

      {scale === "log" && containsZeroOrNegative && (
        <p className="mt-2 text-xs text-muted-foreground">
          Zero-valued opportunities are placed at the chart floor in log view; the text equivalent retains their exact value.
        </p>
      )}

      <details className="mt-3 text-xs">
        <summary className="cursor-pointer font-medium text-foreground">Text equivalent: evidence-ranked opportunity list</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left">
            <caption className="sr-only">Complete evidence-ranked optimization opportunity distribution</caption>
            <thead className="border-b border-border/50 text-muted-foreground">
              <tr>
                <th className="px-1 py-1.5 font-medium">Rank</th>
                <th className="px-1 py-1.5 font-medium">Score</th>
                <th className="px-1 py-1.5 text-right font-medium">Opportunity</th>
                <th className="px-1 py-1.5 text-right font-medium">Disagreement</th>
                <th className="px-1 py-1.5 text-right font-medium">Valid feedback</th>
                <th className="px-1 py-1.5 font-medium">Disposition</th>
                <th className="px-1 py-1.5 font-medium">Reason / availability</th>
              </tr>
            </thead>
            <tbody>
              {points.map(point => (
                <tr key={`${point.evidence_rank}-${point.display_name}`} className="border-b border-border/30 last:border-0">
                  <td className="px-1 py-1.5 tabular-nums">{point.evidence_rank}</td>
                  <td className="px-1 py-1.5 font-medium">
                    {point.dashboard_url
                      ? <a href={point.dashboard_url} className="text-primary hover:underline">{point.display_name}</a>
                      : point.display_name}
                  </td>
                  <td className="px-1 py-1.5 text-right tabular-nums">{formatOpportunity(point.opportunity)}</td>
                  <td className="px-1 py-1.5 text-right tabular-nums">{formatPercentage(point.disagreement_rate)}</td>
                  <td className="px-1 py-1.5 text-right tabular-nums">{formatFeedbackVolume(point.valid_feedback_count)}</td>
                  <td className="px-1 py-1.5">{DISPOSITIONS[point.disposition].label}</td>
                  <td className="px-1 py-1.5 text-muted-foreground">
                    {point.reason || (formatTimestamp(point.eligibility_timestamp) ? `Eligible after ${formatTimestamp(point.eligibility_timestamp)}` : "—")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  )
}

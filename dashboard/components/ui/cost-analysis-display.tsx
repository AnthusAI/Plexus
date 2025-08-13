"use client";

import React from 'react';
import { VictoryChart, VictoryBoxPlot, VictoryTheme, VictoryTooltip, VictoryAxis, VictoryLabel, VictoryHistogram } from 'victory';

export interface CostSummary {
  average_cost?: string;
  count?: number;
  total_cost?: string;
  average_calls?: string | number;
}

export interface CostGroupSummary extends CostSummary {
  group: {
    scoreName?: string;
    scoreId?: string;
    scorecardName?: string;
    scorecardId?: string;
  };
  min_cost?: number;
  q1_cost?: number;
  median_cost?: number;
  q3_cost?: number;
  max_cost?: number;
  values?: number[];
}

export interface CostAnalysisDisplayData {
  block_description?: string;
  scorecardName?: string;
  summary: CostSummary;
  groups?: CostGroupSummary[];
  window?: { hours?: number; days?: number };
  filters?: Record<string, any>;
}

interface Props {
  data: CostAnalysisDisplayData;
  title?: string;
  subtitle?: string;
  attachedFiles?: any;
  log?: string;
  rawOutput?: string;
  id?: string;
  position?: number;
  config?: any;
}

const formatMoney = (v?: string | number) => {
  if (v === undefined || v === null) return '-';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  const truncated = Math.trunc(n * 100000) / 100000; // 5 decimal places, truncate not round
  return `$${truncated.toFixed(5)}`;
};

const formatNumber = (v?: string | number) => {
  if (v === undefined || v === null) return '-';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString();
};

function resolveCssVarColor(varName: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const probe = document.createElement('span');
  probe.style.color = `var(${varName})`;
  // Ensure probe is attached to get computed styles
  document.body.appendChild(probe);
  const computed = getComputedStyle(probe).color;
  document.body.removeChild(probe);
  return computed || fallback;
}

export const CostAnalysisDisplay: React.FC<Props> = ({ data, title, subtitle }) => {
  const overall = data?.summary || {};
  const groups = data?.groups || [];
  const isSingleScore = !!(data?.filters && (data as any).filters?.scoreId) && groups.length === 1;
  // For a horizontal chart, Victory renders the first datum at the bottom.
  // Sort ASC so the highest average cost appears at the top visually.
  const sortedForChart = [...groups].sort((a, b) => Number(a.average_cost || 0) - Number(b.average_cost || 0));
  const boxData = sortedForChart
    .filter(g =>
      [g.min_cost, g.q1_cost, g.median_cost, g.q3_cost, g.max_cost].every(v => typeof v === 'number' && isFinite(v as number))
    )
    .map((g, index) => ({
      // VictoryBoxPlot expects y = [min, q1, median, q3, max]
      x: g.group?.scoreName || g.group?.scoreId || `Score ${index+1}`,
      y: [g.min_cost!, g.q1_cost!, g.median_cost!, g.q3_cost!, g.max_cost!],
    }))
    .slice(0, 100);
  // Dynamically scale chart height by number of scores to avoid label overlap
  const chartHeight = Math.min(8000, Math.max(140, boxData.length * 28 + 100));
  const chartTextColor = React.useMemo(() => {
    if (typeof window === 'undefined') return '#6b7280';
    const isDark = document.documentElement.classList.contains('dark');
    // In light mode, prefer a stronger foreground token for better contrast
    const preferredVar = isDark ? '--foreground' : '--primary-selected-foreground';
    const fallback = isDark ? '#e5e7eb' : '#111827';
    return resolveCssVarColor(preferredVar, fallback);
  }, []);

  const chartFontFamily = React.useMemo(() => {
    if (typeof window === 'undefined') return 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif';
    // Prefer font from <html> (Next/font often applies here), then fall back to body
    const htmlFam = getComputedStyle(document.documentElement).fontFamily;
    if (htmlFam && htmlFam.trim().length > 0) return htmlFam;
    const bodyFam = getComputedStyle(document.body).fontFamily;
    if (bodyFam && bodyFam.trim().length > 0) return bodyFam;
    return 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif';
  }, []);
  const singleHistogramData = isSingleScore
    ? ((groups?.[0] as any)?.values || []).filter((v: any) => typeof v === 'number' && isFinite(v)).map((v: number) => ({ x: v }))
    : [];

  // Determine an adaptive bin count for a more fine-grained histogram
  const histogramBins = (() => {
    if (!isSingleScore) return undefined;
    const raw: number[] = (((groups?.[0] as any)?.values || []) as number[]).filter(v => typeof v === 'number' && isFinite(v));
    const n = raw.length;
    if (n < 2) return undefined;
    const arr = [...raw].sort((a, b) => a - b);
    const min = arr[0];
    const max = arr[arr.length - 1];
    const percentile = (p: number) => {
      const pos = (arr.length - 1) * p;
      const base = Math.floor(pos);
      const rest = pos - base;
      if (arr[base + 1] !== undefined) return arr[base] + rest * (arr[base + 1] - arr[base]);
      return arr[base];
    };
    const q1 = percentile(0.25);
    const q3 = percentile(0.75);
    const iqr = Math.max(0, q3 - q1);
    if (iqr > 0 && max > min) {
      // Narrower bins than classic Freedman–Diaconis: use 1.2 * IQR instead of 2 * IQR
      const binWidth = 1.2 * iqr / Math.cbrt(n);
      const k = Math.ceil((max - min) / binWidth);
      return Math.max(40, Math.min(150, k));
    }
    // Fallback if IQR is zero or degenerate range — still favor narrower bins
    return Math.max(40, Math.min(120, Math.ceil(Math.sqrt(n) * 1.5)));
  })();

  const splitLabelToTwoLines = (label: string, maxCharsPerLine = 18): string => {
    if (!label) return '';
    const words = String(label).split(' ');
    let line1 = '';
    let line2 = '';
    for (const word of words) {
      if ((line1 + (line1 ? ' ' : '') + word).length <= maxCharsPerLine) {
        line1 = line1 ? `${line1} ${word}` : word;
      } else {
        line2 = line2 ? `${line2} ${word}` : word;
      }
    }
    if (!line1 && label.length > maxCharsPerLine) {
      line1 = label.slice(0, maxCharsPerLine);
      line2 = label.slice(maxCharsPerLine);
    }
    return line2 ? `${line1}\n${line2}` : line1;
  };

  return (
    <div className="space-y-4">
      {/* Header intentionally minimal to avoid redundancy with selectors */}

      

      {/* Overall summary */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div className="rounded-md bg-card p-3">
          <div className="text-xs text-muted-foreground">Average cost</div>
          <div className="text-lg font-medium">{formatMoney(overall.average_cost)}</div>
        </div>
        <div className="rounded-md bg-card p-3">
          <div className="text-xs text-muted-foreground">Total cost</div>
          <div className="text-lg font-medium">{formatMoney(overall.total_cost)}</div>
        </div>
        <div className="rounded-md bg-card p-3">
          <div className="text-xs text-muted-foreground">Score results</div>
          <div className="text-lg font-medium">{formatNumber(overall.count)}</div>
        </div>
        <div className="rounded-md bg-card p-3">
          <div className="text-xs text-muted-foreground">Avg LLM calls</div>
          <div className="text-lg font-medium">{formatNumber(overall.average_calls)}</div>
        </div>
      </div>

      {/* Group table (optional) */}
      {groups.length > 0 && (
        <div className="rounded-md overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-primary text-primary-foreground">
                <tr>
                  <th className="text-left p-2">Score</th>
                  <th className="text-left p-2">Average cost</th>
                  <th className="text-left p-2">Total cost</th>
                  <th className="text-right p-2">Score results</th>
                  <th className="text-right p-2">Avg LLM calls</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g, idx) => {
                  const label = g.group?.scoreName || g.group?.scorecardName || g.group?.scoreId || g.group?.scorecardId || `Group ${idx+1}`;
                  return (
                    <tr key={idx} className="odd:bg-card even:bg-background">
                      <td className="p-2">{label}</td>
                      <td className="p-2 text-left font-mono">{formatMoney(g.average_cost)}</td>
                      <td className="p-2 text-left font-mono">{formatMoney(g.total_cost)}</td>
                      <td className="p-2 text-right font-mono">{formatNumber(g.count)}</td>
                      <td className="p-2 text-right font-mono">{formatNumber(g.average_calls)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Box Plot (scorecard-level) */}
      {boxData.length > 0 && (
        <div className="rounded-md bg-card p-3" data-testid="cost-boxplot">
          <div className="text-sm font-medium mb-2">{isSingleScore ? 'Box Plot' : 'Cost distribution per score'}</div>
          <div className="w-full overflow-x-auto">
            <div style={{ minWidth: 480 }}>
              <VictoryChart
                horizontal
                domainPadding={20}
                theme={VictoryTheme.clean}
                height={chartHeight}
                padding={{ top: 20, bottom: 60, left: 140, right: 20 }}
              >
                {/* Left-side category axis with wrapped labels */}
                <VictoryAxis
                  orientation="left"
                  tickValues={boxData.map(d => d.x as any)}
                  tickFormat={(t: any) => splitLabelToTwoLines(String(t))}
                  tickLabelComponent={<VictoryLabel lineHeight={1.1} style={{ fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily }} />}
                  style={{
                    axis: { stroke: chartTextColor },
                    tickLabels: { fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily },
                    ticks: { stroke: chartTextColor },
                    grid: { stroke: 'transparent' },
                  }}
                />
                {/* Bottom numeric axis for value ticks */}
                <VictoryAxis
                  dependentAxis
                  orientation="bottom"
                  tickFormat={(t) => `$${Number(t).toFixed(2)}`}
                  style={{
                    axis: { stroke: chartTextColor },
                    tickLabels: { fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily },
                    ticks: { stroke: chartTextColor },
                    grid: { stroke: 'transparent' },
                  }}
                />
                <VictoryBoxPlot
                  data={boxData}
                  boxWidth={12}
                  // Enable labels for all metrics so tooltips can activate
                  minLabels={({ datum }: any) => formatMoney(datum?.y?.[0])}
                  q1Labels={({ datum }: any) => formatMoney(datum?.y?.[1])}
                  medianLabels={({ datum }: any) => formatMoney(datum?.y?.[2])}
                  q3Labels={({ datum }: any) => formatMoney(datum?.y?.[3])}
                  maxLabels={({ datum }: any) => formatMoney(datum?.y?.[4])}
                  // Tooltip components for each metric
                  minLabelComponent={
                    <VictoryTooltip
                      constrainToVisibleArea
                      flyoutStyle={{ fill: 'var(--card)', stroke: 'var(--muted-foreground)' }}
                      style={{ fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily }}
                    />
                  }
                  q1LabelComponent={
                    <VictoryTooltip
                      constrainToVisibleArea
                      flyoutStyle={{ fill: 'var(--card)', stroke: 'var(--muted-foreground)' }}
                      style={{ fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily }}
                    />
                  }
                  medianLabelComponent={
                    <VictoryTooltip
                      constrainToVisibleArea
                      flyoutStyle={{ fill: 'var(--card)', stroke: 'var(--muted-foreground)' }}
                      style={{ fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily }}
                    />
                  }
                  q3LabelComponent={
                    <VictoryTooltip
                      constrainToVisibleArea
                      flyoutStyle={{ fill: 'var(--card)', stroke: 'var(--muted-foreground)' }}
                      style={{ fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily }}
                    />
                  }
                  maxLabelComponent={
                    <VictoryTooltip
                      constrainToVisibleArea
                      flyoutStyle={{ fill: 'var(--card)', stroke: 'var(--muted-foreground)' }}
                      style={{ fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily }}
                    />
                  }
                  style={{
                    // Ensure all segments receive pointer events for hover activation
                    min: { pointerEvents: 'all' },
                    max: { pointerEvents: 'all' },
                    q1: { pointerEvents: 'all' },
                    q3: { pointerEvents: 'all' },
                    median: { pointerEvents: 'all' },
                  } as any}
                  // Activate the corresponding tooltip on hover / focus / touch
                  events={(['min', 'q1', 'median', 'q3', 'max'] as const).map((dataType) => ({
                    target: dataType as any,
                    eventHandlers: {
                      onMouseOver: () => [
                        { target: `${dataType}Labels` as any, mutation: () => ({ active: true }) },
                      ],
                      onFocus: () => [
                        { target: `${dataType}Labels` as any, mutation: () => ({ active: true }) },
                      ],
                      onTouchStart: () => [
                        { target: `${dataType}Labels` as any, mutation: () => ({ active: true }) },
                      ],
                      onMouseOut: () => [
                        { target: `${dataType}Labels` as any, mutation: () => ({ active: undefined }) },
                      ],
                      onBlur: () => [
                        { target: `${dataType}Labels` as any, mutation: () => ({ active: undefined }) },
                      ],
                      onTouchEnd: () => [
                        { target: `${dataType}Labels` as any, mutation: () => ({ active: undefined }) },
                      ],
                    },
                  })) as any}
                />
              </VictoryChart>
            </div>
          </div>
        </div>
      )}

      {/* Histogram (single-score only) */}
      {isSingleScore && singleHistogramData.length > 0 && (
        <div className="rounded-md bg-card p-3" data-testid="cost-histogram">
          <div className="text-sm font-medium mb-2">Histogram</div>
          <div className="w-full overflow-x-auto">
            <div style={{ minWidth: 480 }}>
              <VictoryChart
                domainPadding={20}
                theme={VictoryTheme.clean}
                height={260}
                padding={{ top: 20, bottom: 60, left: 60, right: 20 }}
              >
                <VictoryAxis
                  orientation="bottom"
                  tickFormat={(t) => `$${Number(t).toFixed(2)}`}
                  style={{
                    axis: { stroke: chartTextColor },
                    tickLabels: { fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily },
                    ticks: { stroke: chartTextColor },
                  }}
                />
                <VictoryAxis
                  dependentAxis
                  style={{
                    axis: { stroke: chartTextColor },
                    tickLabels: { fontSize: 10, fill: chartTextColor, fontFamily: chartFontFamily },
                    ticks: { stroke: chartTextColor },
                  }}
                />
                <VictoryHistogram
                  data={singleHistogramData}
                  bins={histogramBins}
                  binSpacing={1}
                  style={{
                    data: {
                      fill: 'var(--primary-selected)',
                      fillOpacity: 1,
                      stroke: 'var(--primary-selected)',
                      strokeWidth: 0,
                    },
                    labels: { fontSize: 10 },
                  }}
                  labels={({ datum }: any) => {
                    const left = (datum as any)?.x0 ?? (datum as any)?.x;
                    const right = (datum as any)?.x1 ?? (datum as any)?.x;
                    const leftStr = typeof left === 'number' ? formatMoney(left) : String(left);
                    const rightStr = typeof right === 'number' ? formatMoney(right) : String(right);
                    return `Bin ${leftStr} – ${rightStr}\nCount: ${datum.y}`;
                  }}
                  labelComponent={<VictoryTooltip constrainToVisibleArea style={{ fontSize: 10 }} flyoutStyle={{ fill: 'var(--card)', stroke: 'var(--muted-foreground)' }} />}
                />
              </VictoryChart>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CostAnalysisDisplay;



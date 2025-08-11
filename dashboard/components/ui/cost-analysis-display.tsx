import React from 'react';

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
  return `$${n.toFixed(6)}`;
};

const formatNumber = (v?: string | number) => {
  if (v === undefined || v === null) return '-';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString();
};

export const CostAnalysisDisplay: React.FC<Props> = ({ data, title, subtitle }) => {
  const overall = data?.summary || {};
  const groups = data?.groups || [];

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
    </div>
  );
};

export default CostAnalysisDisplay;



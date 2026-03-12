import React from 'react';
import { ReportBlockProps } from './ReportBlock';
import { CostAnalysisDisplay, type CostAnalysisDisplayData } from '@/components/ui/cost-analysis-display';
import * as yaml from 'js-yaml';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ChevronUp, ChevronDown } from 'lucide-react';

export interface CostAnalysisData extends CostAnalysisDisplayData {}

type AllScorecardsCostAnalysisScorecard = CostAnalysisDisplayData & {
  scorecard_id?: string;
  scorecard_name?: string;
  scorecard_external_id?: string | null;
  rank?: number;
};

type AllScorecardsCostAnalysisOutput = {
  mode: 'all_scorecards';
  block_title?: string;
  block_description?: string;
  message?: string;
  total_scorecards_analyzed?: number;
  total_scorecards_with_data?: number;
  total_scorecards_without_data?: number;
  date_range?: { start: string; end: string };
  window?: { hours?: number | null; days?: number | null };
  scorecards?: AllScorecardsCostAnalysisScorecard[];
};

const formatMoney = (v?: string | number) => {
  if (v === undefined || v === null) return '-';
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  const truncated = Math.trunc(n * 100000) / 100000; // 5 dp, truncate not round
  return `$${truncated.toFixed(5)}`;
};

function safeNumber(v: any): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function isAllScorecardsCostAnalysisOutput(value: any): value is AllScorecardsCostAnalysisOutput {
  return !!value && typeof value === 'object' && (value as any).mode === 'all_scorecards';
}

const CostAnalysis: React.FC<ReportBlockProps> = (props) => {
  if (!props.output) {
    return <p>No cost analysis data available or data is loading.</p>;
  }

  let data: CostAnalysisData | AllScorecardsCostAnalysisOutput;
  try {
    if (typeof props.output === 'string') {
      data = yaml.load(props.output) as CostAnalysisData;
    } else {
      data = props.output as CostAnalysisData;
    }
  } catch (error) {
    console.error('❌ CostAnalysis: Failed to parse output data:', error);
    return (
      <div className="p-4 text-center text-destructive">
        Error parsing cost analysis data. Please check the report generation.
      </div>
    );
  }

  const title = (props.name && !props.name.startsWith('block_')) ? props.name : 'Cost Analysis';

  const allScorecardsData = isAllScorecardsCostAnalysisOutput(data) ? data : null;
  const isAllScorecardsMode = !!allScorecardsData;
  const [expandedScorecardId, setExpandedScorecardId] = React.useState<string | null>(null);
  const [sortBy, setSortBy] = React.useState<'total_cost' | 'avg_cost_per_item'>('total_cost');

  const allScorecards = Array.isArray(allScorecardsData?.scorecards) ? allScorecardsData!.scorecards! : [];
  const sortedAllScorecards = React.useMemo(() => {
    if (!isAllScorecardsMode) return [];
    const copy = [...allScorecards];
    const getTotal = (s: AllScorecardsCostAnalysisScorecard) =>
      safeNumber((s as any)?.summary?.total_cost ?? (s as any)?.itemAnalysis?.total_cost);
    const getAvgItem = (s: AllScorecardsCostAnalysisScorecard) =>
      safeNumber((s as any)?.itemAnalysis?.average_cost);

    copy.sort((a, b) => {
      const primary = sortBy === 'total_cost' ? (getTotal(b) - getTotal(a)) : (getAvgItem(b) - getAvgItem(a));
      if (primary !== 0) return primary;
      const an = String((a as any)?.scorecard_name ?? '').toLowerCase();
      const bn = String((b as any)?.scorecard_name ?? '').toLowerCase();
      return an.localeCompare(bn);
    });
    return copy;
  }, [isAllScorecardsMode, allScorecards, sortBy]);

  // All scorecards mode (aka "all costs")
  if (isAllScorecardsMode) {
    const allData = allScorecardsData;
    const sorted = sortedAllScorecards;

    const range = allData.date_range;
    const rangeLabel = range?.start && range?.end
      ? `${new Date(range.start).toLocaleString()} – ${new Date(range.end).toLocaleString()}`
      : null;

    return (
      <div className="space-y-6">
        <div className="p-4 bg-muted/30 rounded-lg">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold mb-1">{title}</h3>
              {allData.block_description && (
                <p className="text-sm text-muted-foreground">{allData.block_description}</p>
              )}
              <div className="text-sm text-muted-foreground mt-2 space-y-1">
                <div>
                  <strong className="text-foreground">Scorecards:</strong>{' '}
                  {allData.total_scorecards_analyzed ?? allScorecards.length}
                  {allData.total_scorecards_with_data !== undefined && (
                    <span>
                      {' '}(<span className="text-foreground">{allData.total_scorecards_with_data}</span> with data,{' '}
                      <span className="text-foreground">{allData.total_scorecards_without_data ?? 0}</span> without)
                    </span>
                  )}
                </div>
                {rangeLabel && (
                  <div><strong className="text-foreground">Date range:</strong> {rangeLabel}</div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="text-sm text-muted-foreground whitespace-nowrap">Sort:</div>
              <Select value={sortBy} onValueChange={(v) => setSortBy(v as any)}>
                <SelectTrigger className="w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="total_cost">Highest total cost</SelectItem>
                  <SelectItem value="avg_cost_per_item">Highest avg cost per item</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {sorted.length === 0 ? (
          <p className="text-muted-foreground">No scorecards found.</p>
        ) : (
          <div className="space-y-4">
	            {sorted.map((scorecardData, index) => {
	              const scorecardId = String(scorecardData.scorecard_id ?? index);
	              const isExpanded = expandedScorecardId === scorecardId;
	              const totalCost = safeNumber((scorecardData as any)?.summary?.total_cost ?? (scorecardData as any)?.itemAnalysis?.total_cost);
	              const avgPerItem = safeNumber((scorecardData as any)?.itemAnalysis?.average_cost);
	              const itemCount = safeNumber((scorecardData as any)?.itemAnalysis?.count);

	              return (
	                <div key={scorecardId}>
	                  <div className="rounded-lg border bg-card p-4 shadow-sm hover:shadow transition-shadow">
	                    <div className="flex items-start justify-between gap-4">
	                      <div className="flex items-start gap-4 flex-1">
	                        <span className="text-sm text-muted-foreground font-mono pt-1">#{index + 1}</span>
	                        <div className="flex-1">
	                          <div className="font-semibold mb-1">{(scorecardData as any)?.scorecard_name || scorecardId}</div>
	                        </div>
	                      </div>

	                      <div className="flex items-center gap-6">
	                        <div className="text-right">
	                          <div className="text-xs text-muted-foreground">Total cost</div>
	                          <div className="text-lg font-medium font-mono">{formatMoney(totalCost)}</div>
	                        </div>
	                        <div className="text-right">
	                          <div className="text-xs text-muted-foreground">Avg cost / item</div>
	                          <div className="text-lg font-medium font-mono">{formatMoney(avgPerItem)}</div>
	                        </div>
	                        <div className="text-right">
	                          <div className="text-xs text-muted-foreground">Item count</div>
	                          <div className="text-lg font-medium font-mono">{itemCount.toLocaleString()}</div>
	                        </div>
	                      </div>
	                    </div>

                    <div className="flex flex-col items-center mt-4">
                      <div className="w-full h-px bg-border mb-1"></div>
                      <button
                        onClick={() => setExpandedScorecardId(isExpanded ? null : scorecardId)}
                        className="flex items-center justify-center rounded-full hover:bg-muted/50 transition-colors"
                        aria-label={isExpanded ? "Collapse details" : "Expand details"}
                      >
                        {isExpanded ? (
                          <ChevronUp className="h-3 w-3 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="h-3 w-3 text-muted-foreground" />
                        )}
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="pt-3">
                      <CostAnalysisDisplay
                        data={scorecardData}
                        title={(scorecardData as any)?.scorecard_name}
                        subtitle={(scorecardData as any)?.block_description}
                        attachedFiles={props.attachedFiles}
                        log={props.log}
                        rawOutput={typeof props.output === 'string' ? props.output : undefined}
                        id={`${props.id}-${index}`}
                        position={props.position}
                        config={props.config}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  const singleData = data as CostAnalysisData;
  return (
    <CostAnalysisDisplay
      data={singleData}
      title={title}
      subtitle={singleData.block_description}
      attachedFiles={props.attachedFiles}
      log={props.log}
      rawOutput={typeof props.output === 'string' ? props.output : undefined}
      id={props.id}
      position={props.position}
      config={props.config}
    />
  );
};

(CostAnalysis as any).blockClass = 'CostAnalysis';

export default CostAnalysis;

"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";
import { ChevronDown, ChevronRight } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

import { parseOutputString } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { IdentifierDisplay } from "@/components/ui/identifier-display";
import { ScoreResultTrace } from "@/components/ui/score-result-trace";

import ReportBlock, { ReportBlockProps, type BlockComponent } from "./ReportBlock";

interface ScoreResultRow {
  input_identifier?: string;
  resolved_item_id?: string;
  item_identifiers?: Array<{ name: string; value: string; url?: string }> | null;
  status?: string;
  score_result_id?: string | null;
  value?: string | null;
  explanation?: string | null;
  cost?: unknown;
  trace?: unknown;
  error?: string | null;
}

interface CostSummary {
  totalCostUsd?: number;
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
}

interface ScoreResultScoreSection {
  score_id: string;
  score_name: string;
  results?: ScoreResultRow[];
}

interface ScoreResultsReportData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
  scope?: "single_score" | "scorecard_all_scores";
  scorecard_name?: string | null;
  score_name?: string | null;
  summary?: {
    input_identifier_count?: number;
    resolved_item_count?: number;
    unresolved_identifier_count?: number;
    scores_analyzed?: number;
    total_predictions?: number;
    successful_predictions?: number;
    failed_predictions?: number;
  };
  scores?: ScoreResultScoreSection[];
  unresolved_identifiers?: Array<{ input_identifier?: string; error?: string }>;
  failed_predictions?: Array<{
    input_identifier?: string;
    score_name?: string;
    error?: string;
  }>;
  error?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

const parseCostSummary = (value: unknown): CostSummary | null => {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return { totalCostUsd: value };
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? { totalCostUsd: parsed } : null;
  }
  if (typeof value !== "object") return null;

  const data = value as Record<string, unknown>;
  const totalCostRaw = data.total_cost ?? data.totalCost ?? data.usd;
  const promptTokensRaw = data.prompt_tokens ?? data.promptTokens;
  const completionTokensRaw = data.completion_tokens ?? data.completionTokens;
  const totalTokensRaw = data.total_tokens ?? data.totalTokens;

  const toNumber = (input: unknown): number | undefined => {
    if (typeof input === "number" && Number.isFinite(input)) return input;
    if (typeof input === "string") {
      const parsed = Number(input);
      if (Number.isFinite(parsed)) return parsed;
    }
    return undefined;
  };

  const promptTokens = toNumber(promptTokensRaw);
  const completionTokens = toNumber(completionTokensRaw);
  const totalTokens = toNumber(totalTokensRaw) ?? (
    promptTokens !== undefined || completionTokens !== undefined
      ? (promptTokens ?? 0) + (completionTokens ?? 0)
      : undefined
  );

  return {
    totalCostUsd: toNumber(totalCostRaw),
    promptTokens,
    completionTokens,
    totalTokens,
  };
};

const formatUsd = (value?: number): string | null => {
  if (value === undefined || !Number.isFinite(value)) return null;
  if (value === 0) return "$0.00";
  if (Math.abs(value) < 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(2)}`;
};

const formatTokenCount = (value?: number): string | null => {
  if (value === undefined || !Number.isFinite(value)) return null;
  return `${Math.round(value).toLocaleString()} tok`;
};

const ScoreResultsReport: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<ScoreResultsReportData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);
  const [expandedTraceKeys, setExpandedTraceKeys] = React.useState<Record<string, boolean>>({});

  let parsedOutput: ScoreResultsReportData = {};
  try {
    parsedOutput =
      typeof props.output === "string"
        ? (parseOutputString(props.output) as ScoreResultsReportData)
        : ((props.output || {}) as ScoreResultsReportData);
  } catch {
    parsedOutput = {};
  }

  const isCompacted = Boolean(parsedOutput?.output_compacted && parsedOutput?.output_attachment);

  React.useEffect(() => {
    let cancelled = false;
    if (!isCompacted || !parsedOutput.output_attachment) {
      setLoadedOutput(null);
      setAttachmentLoadError(null);
      return;
    }

    (async () => {
      try {
        const downloaded = await downloadData({
          path: parsedOutput.output_attachment as string,
          options: { bucket: "reportBlockDetails" },
        }).result;
        const text = await downloaded.body.text();
        if (!cancelled) setLoadedOutput(parseOutputString(text) as ScoreResultsReportData);
        if (!cancelled) setAttachmentLoadError(null);
      } catch {
        if (!cancelled) {
          setAttachmentLoadError("Failed to load compacted output attachment.");
          setLoadedOutput(null);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isCompacted, parsedOutput.output_attachment]);

  const output = loadedOutput || parsedOutput;
  const candidateTitle = output.block_title || props.name || "Score Results Report";
  const blockTitle =
    output.score_name && candidateTitle?.trim() === output.score_name?.trim()
      ? "Score Results Report"
      : candidateTitle;
  const rawSubtitle = output.scorecard_name || undefined;
  const subtitle = rawSubtitle && rawSubtitle !== blockTitle ? rawSubtitle : undefined;
  const scores = Array.isArray(output.scores) ? output.scores : [];
  const scoreResultCount = scores.reduce((count, score) => count + (score.results?.length ?? 0), 0);
  const scoreCount = scores.length;
  const promptTokenValues = scores.flatMap((score) =>
    (score.results || [])
      .map((row) => parseCostSummary(row.cost)?.promptTokens)
      .filter((tokens): tokens is number => typeof tokens === "number" && Number.isFinite(tokens))
  );
  const completionTokenValues = scores.flatMap((score) =>
    (score.results || [])
      .map((row) => parseCostSummary(row.cost)?.completionTokens)
      .filter((tokens): tokens is number => typeof tokens === "number" && Number.isFinite(tokens))
  );
  const totalPromptTokens = promptTokenValues.reduce((sum, value) => sum + value, 0);
  const totalCompletionTokens = completionTokenValues.reduce((sum, value) => sum + value, 0);
  const costValues = scores.flatMap((score) =>
    (score.results || [])
      .map((row) => parseCostSummary(row.cost)?.totalCostUsd)
      .filter((cost): cost is number => typeof cost === "number" && Number.isFinite(cost))
  );
  const totalCostUsd = costValues.reduce((sum, value) => sum + value, 0);
  const totalCostLabel = costValues.length > 0 ? (formatUsd(totalCostUsd) ?? "N/A") : "N/A";
  const showInBlockHeaderRow = (() => {
    const scorecard = output.scorecard_name?.trim();
    const score = output.score_name?.trim();
    if (!scorecard && !score) return false;
    if (score) return false;
    if (scorecard && scorecard !== blockTitle && scorecard !== subtitle) return true;
    return false;
  })();
  const isLoadingCompactedOutput = isCompacted && !loadedOutput && !attachmentLoadError;
  const hasResolvedData =
    scores.length > 0 ||
    Boolean(output.summary) ||
    Boolean(output.error) ||
    Boolean((output.unresolved_identifiers || []).length) ||
    Boolean((output.failed_predictions || []).length);

  if ((output.error || attachmentLoadError) && !isLoadingCompactedOutput) {
    return (
      <ReportBlock {...props} output={output} title={output.block_title || props.name || "Score Results Report"} subtitle={subtitle}>
        <div className="p-4 text-sm text-red-600 dark:text-red-400" data-testid="score-results-report-error">
          {output.error || attachmentLoadError}
        </div>
      </ReportBlock>
    );
  }

  if (isLoadingCompactedOutput && !hasResolvedData) {
    return (
      <ReportBlock {...props} output={output} title={output.block_title || props.name || "Score Results Report"} subtitle={subtitle}>
        <div className="p-4 text-sm text-muted-foreground" data-testid="score-results-report-loading">
          Report block is loading detailed output.
        </div>
      </ReportBlock>
    );
  }

  return (
    <ReportBlock {...props} output={output} title={blockTitle} subtitle={subtitle}>
      <div className="space-y-4" data-testid="score-results-report">
        {showInBlockHeaderRow ? (
          <div className="rounded-md bg-muted/40 px-3 py-2" data-testid="score-results-header-row">
            <div className="text-sm font-semibold">{output.scorecard_name || "Scorecard"}</div>
            {output.score_name ? <div className="text-xs text-muted-foreground">{output.score_name}</div> : null}
          </div>
        ) : null}
        <div className="rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground" data-testid="score-results-summary">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            {scoreCount > 1 ? <span>Scores: {scoreCount}</span> : null}
            <span>Score Results: {scoreResultCount}</span>
            {promptTokenValues.length > 0 ? <span>Input Tokens: {Math.round(totalPromptTokens).toLocaleString()}</span> : null}
            {completionTokenValues.length > 0 ? <span>Output Tokens: {Math.round(totalCompletionTokens).toLocaleString()}</span> : null}
            <span>Total Cost: {totalCostLabel}</span>
          </div>
        </div>

        {(output.unresolved_identifiers || []).length > 0 ? (
          <section data-testid="unresolved-identifiers" className="rounded-md bg-muted/40 p-3">
            <div className="mb-2 text-sm font-medium">Unresolved Identifiers</div>
            <ul className="space-y-1 text-xs">
              {(output.unresolved_identifiers || []).map((entry, index) => (
                <li key={`${entry.input_identifier || "unknown"}-${index}`}>
                  <span className="font-medium">{entry.input_identifier || "Unknown"}:</span>{" "}
                  {entry.error || "No item found"}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {scores.map((score) => (
          <section key={score.score_id} className="overflow-hidden rounded-md bg-muted/30" data-testid={`score-section-${score.score_id}`}>
            <div className="bg-muted/40 px-3 py-2 text-sm font-semibold">{score.score_name}</div>
            <div className="space-y-2 py-2">
              {(score.results || []).map((row, rowIndex) => {
                const key = `${score.score_id}-${row.input_identifier || "unknown"}-${rowIndex}`;
                const traceExpanded = Boolean(expandedTraceKeys[key]);
                const status = row.status || "unknown";
                const cost = parseCostSummary(row.cost);
                const usd = formatUsd(cost?.totalCostUsd);
                const promptTokens = formatTokenCount(cost?.promptTokens);
                const completionTokens = formatTokenCount(cost?.completionTokens);
                return (
                  <article key={key} className="rounded-md bg-card-light px-3 py-2" data-testid={`result-row-${key}`}>
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="secondary"
                          className="bg-muted text-muted-foreground"
                        >
                          {row.value ?? (status === "failed" ? "Failed" : "N/A")}
                        </Badge>
                        {status !== "success" ? (
                          <span className="text-xs text-muted-foreground">Status {status}</span>
                        ) : null}
                        {row.trace ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-6 px-1 text-xs"
                            onClick={() =>
                              setExpandedTraceKeys((current) => ({ ...current, [key]: !current[key] }))
                            }
                            data-testid={`trace-toggle-${key}`}
                          >
                            {traceExpanded ? <ChevronDown className="mr-1 h-3 w-3" /> : <ChevronRight className="mr-1 h-3 w-3" />}
                            Trace
                          </Button>
                        ) : null}
                      </div>
                      <div className="space-y-1">
                        <IdentifierDisplay
                          identifiers={row.item_identifiers ?? undefined}
                          externalId={row.resolved_item_id || undefined}
                          displayMode="full"
                          textSize="xs"
                        />
                      </div>
                    </div>
                    <div className="mt-2 rounded-md bg-background p-2">
                      <div className="prose prose-sm max-w-none text-muted-foreground prose-p:mb-0 prose-p:text-muted-foreground">
                        <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                          {row.explanation || row.error || "No explanation provided."}
                        </ReactMarkdown>
                      </div>
                    </div>
                    {traceExpanded ? (
                      <div className="mt-2 rounded-md bg-background p-2" data-testid={`trace-content-${key}`}>
                        <ScoreResultTrace trace={row.trace} variant="compact" />
                      </div>
                    ) : null}
                    <div className="mt-2 text-xs text-muted-foreground">
                      {!cost ? (
                        "Cost N/A"
                      ) : !usd && !promptTokens && !completionTokens ? (
                        "Cost available"
                      ) : (
                        <>
                          Cost {usd ?? "N/A"}
                          {promptTokens ? ` · In ${promptTokens}` : ""}
                          {completionTokens ? ` · Out ${completionTokens}` : ""}
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </ReportBlock>
  );
};

(ScoreResultsReport as BlockComponent).blockClass = "ScoreResultsReport";

export default ScoreResultsReport;

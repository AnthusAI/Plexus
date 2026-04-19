"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";

import { parseOutputString } from "@/lib/utils";
import ReportBlock, { ReportBlockProps } from "./ReportBlock";
import { useIncrementalRows } from "./useIncrementalRows";
import { IdentifierDisplay } from "@/components/ui/identifier-display";
import { Timestamp } from "@/components/ui/timestamp";

interface AcceptanceSummary {
  total_items: number;
  accepted_items: number;
  corrected_items: number;
  item_acceptance_rate: number;
  total_score_results: number;
  accepted_score_results: number;
  corrected_score_results: number;
  score_result_acceptance_rate: number;
  feedback_items_total: number;
  feedback_items_valid: number;
  feedback_items_changed: number;
  score_results_with_feedback: number;
}

interface AcceptanceItem {
  item_id: string;
  item_external_id?: string | null;
  item_created_at?: string | null;
  item_updated_at?: string | null;
  item_identifiers?: string | Record<string, string> | Array<{ name: string; value: string; url?: string }> | null;
  item_accepted: boolean;
  total_score_results: number;
  accepted_score_results: number;
  corrected_score_results: number;
  feedback_items_total?: number;
  feedback_items_valid?: number;
  feedback_scores_with_feedback_count?: number;
  score_result_acceptance_rate: number;
}

interface AcceptanceRateData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
  include_item_acceptance_rate?: boolean;
  max_items?: number;
  items_total?: number;
  items_returned?: number;
  items_truncated?: boolean;
  scorecard_name?: string;
  score_name?: string | null;
  date_range?: {
    start: string;
    end: string;
  };
  summary?: AcceptanceSummary;
  items?: AcceptanceItem[];
  error?: string;
  warning?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

const formatPercent = (value: number | undefined): string => {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return "0.00%";
  }
  return `${(value * 100).toFixed(2)}%`;
};

const AUTO_SHOW_ROWS_THRESHOLD = 200;

const AcceptanceRate: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<AcceptanceRateData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);

  let parsedOutput: AcceptanceRateData = {};
  try {
    parsedOutput =
      typeof props.output === "string"
        ? (parseOutputString(props.output) as AcceptanceRateData)
        : ((props.output || {}) as AcceptanceRateData);
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
        const result = await downloadData({
          path: parsedOutput.output_attachment!,
          options: { bucket: "reportBlockDetails" as any },
        }).result;
        const text = await result.body.text();
        if (!cancelled) {
          setLoadedOutput(parseOutputString(text) as AcceptanceRateData);
        }
      } catch (error) {
        if (!cancelled) {
          setAttachmentLoadError(
            error instanceof Error ? error.message : "Failed to load compacted output attachment."
          );
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loadedOutput, parsedOutput.output_attachment, parsedOutput.output_compacted]);

  const output = loadedOutput ?? parsedOutput;
  const summary = output.summary;
  const items = Array.isArray(output.items) ? output.items : [];
  const [showRows, setShowRows] = React.useState(items.length <= AUTO_SHOW_ROWS_THRESHOLD);

  React.useEffect(() => {
    setShowRows(items.length <= AUTO_SHOW_ROWS_THRESHOLD);
  }, [items.length]);

  const {
    visibleRows,
    visibleCount,
    totalCount,
    hasMore,
    loadMore,
    sentinelRef,
  } = useIncrementalRows(items, { initialCount: 100, pageSize: 100 });
  const showItemAcceptance =
    output.include_item_acceptance_rate ?? summary?.item_acceptance_rate !== undefined;
  const title =
    props.name && !props.name.startsWith("block_")
      ? props.name
      : output.block_title || "Acceptance Rate";

  return (
    <ReportBlock
      {...props}
      output={output as any}
      title={title}
      subtitle={output.block_description}
      error={attachmentLoadError || output.error}
      warning={output.warning}
      dateRange={output.date_range}
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {showItemAcceptance ? (
            <div className="rounded-md bg-card p-3">
              <div className="text-xs text-muted-foreground">Item Acceptance Rate</div>
              <div className="text-xl font-semibold">{formatPercent(summary?.item_acceptance_rate)}</div>
            </div>
          ) : null}
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Score-Result Acceptance Rate</div>
            <div className="text-xl font-semibold">
              {formatPercent(summary?.score_result_acceptance_rate)}
            </div>
          </div>
          {showItemAcceptance ? (
            <div className="rounded-md bg-card p-3">
              <div className="text-xs text-muted-foreground">Accepted Items</div>
              <div className="text-xl font-semibold">
                {(summary?.accepted_items ?? 0)} / {(summary?.total_items ?? 0)}
              </div>
            </div>
          ) : null}
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Accepted Score Results</div>
            <div className="text-xl font-semibold">
              {(summary?.accepted_score_results ?? 0)} / {(summary?.total_score_results ?? 0)}
            </div>
          </div>
          <div className="rounded-md bg-card p-3">
            <div className="text-xs text-muted-foreground">Feedback Edits</div>
            <div className="text-xl font-semibold">{summary?.feedback_items_total ?? 0}</div>
            <div className="text-xs text-muted-foreground">
              Valid: {summary?.feedback_items_valid ?? 0}
            </div>
            <div className="text-xs text-muted-foreground">
              Value changed: {summary?.feedback_items_changed ?? 0}
            </div>
          </div>
        </div>

        <div className="text-sm text-muted-foreground">
          {output.scorecard_name ? `Scorecard: ${output.scorecard_name}` : null}
          {output.score_name ? ` • Score: ${output.score_name}` : null}
          {summary ? ` • Feedback edits: ${summary.feedback_items_valid ?? 0}/${summary.feedback_items_total ?? 0}` : null}
          {summary ? ` • Value-changing edits: ${summary.feedback_items_changed ?? 0}` : null}
          {output.items_truncated
            ? ` • Showing ${output.items_returned ?? items.length} of ${output.items_total ?? "?"} items`
            : null}
          {totalCount > 0 ? ` • Rendering ${visibleCount} of ${totalCount} rows` : null}
        </div>

        {items.length > AUTO_SHOW_ROWS_THRESHOLD && !showRows ? (
          <div className="rounded-md border bg-card p-4">
            <div className="text-sm text-muted-foreground">
              Item rows are hidden by default for large results.
            </div>
            <button
              type="button"
              onClick={() => setShowRows(true)}
              className="mt-3 rounded-md border bg-card px-3 py-1.5 text-xs font-medium hover:bg-card-selected"
            >
              Show item rows ({items.length})
            </button>
          </div>
        ) : null}
        {showRows ? (
          <>
            <div className="overflow-x-auto rounded-md bg-card">
              <table className="w-full text-sm">
                <thead className="bg-card-selected">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium whitespace-nowrap">Item Date</th>
                    <th className="px-3 py-2 text-left font-medium">Item Identifiers</th>
                    <th className="px-3 py-2 text-right font-medium">Feedback Edits</th>
                    <th className="px-3 py-2 text-right font-medium whitespace-nowrap">Score Results</th>
                    <th className="px-3 py-2 text-right font-medium">Accepted</th>
                    <th className="px-3 py-2 text-right font-medium">Corrected</th>
                    <th className="px-3 py-2 text-right font-medium whitespace-nowrap">Score Result Acceptance Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                        No score results matched the requested filters.
                      </td>
                    </tr>
                  ) : (
                    visibleRows.map((item, index) => (
                      <tr
                        key={item.item_id}
                        className={index % 2 === 0 ? "bg-card" : "bg-card-selected/60"}
                      >
                        <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">
                          {item.item_created_at ? (
                            <Timestamp
                              time={item.item_created_at}
                              variant="relative"
                              showIcon={true}
                              className="text-xs"
                            />
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-3 py-2 align-top">
                          <IdentifierDisplay
                            identifiers={item.item_identifiers ?? undefined}
                            externalId={item.item_external_id ?? item.item_id}
                            displayMode="full"
                            textSize="xs"
                          />
                        </td>
                        <td className="px-3 py-2 text-right">
                          {(item.feedback_items_valid ?? 0)}/{(item.feedback_items_total ?? 0)}
                        </td>
                        <td className="px-3 py-2 text-right">{item.total_score_results}</td>
                        <td className="px-3 py-2 text-right">{item.accepted_score_results}</td>
                        <td className="px-3 py-2 text-right">{item.corrected_score_results}</td>
                        <td className="px-3 py-2 text-right">
                          {formatPercent(item.score_result_acceptance_rate)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {items.length > 0 ? (
              <div className="flex items-center justify-between gap-3">
                <div ref={sentinelRef} className="h-1 w-1" aria-hidden="true" />
                {hasMore ? (
                  <button
                    type="button"
                    onClick={loadMore}
                    className="rounded-md border bg-card px-3 py-1.5 text-xs font-medium hover:bg-card-selected"
                  >
                    Load more rows ({visibleCount}/{totalCount})
                  </button>
                ) : (
                  <span className="text-xs text-muted-foreground">All rows loaded ({totalCount})</span>
                )}
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </ReportBlock>
  );
};

export default AcceptanceRate;

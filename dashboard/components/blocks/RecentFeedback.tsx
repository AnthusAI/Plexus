"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";

import { parseOutputString } from "@/lib/utils";
import ReportBlock, { ReportBlockProps } from "./ReportBlock";
import { useIncrementalRows } from "./useIncrementalRows";

interface RecentFeedbackSummary {
  total_feedback_items: number;
  corrected_feedback_items: number;
  agreed_feedback_items: number;
  invalid_feedback_items: number;
  distinct_items_count: number;
  distinct_score_count: number;
}

interface RecentFeedbackItem {
  feedback_item_id: string;
  item_id: string;
  score_id: string;
  score_name?: string;
  initial_value?: string | null;
  final_value?: string | null;
  corrected: boolean;
  is_invalid: boolean;
  edited_at?: string | null;
  edit_comment?: string | null;
}

interface RecentFeedbackData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
  scorecard_name?: string;
  score_name?: string | null;
  date_range?: {
    start: string;
    end: string;
  };
  summary?: RecentFeedbackSummary;
  items?: RecentFeedbackItem[];
  error?: string;
  warning?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

const AUTO_SHOW_ROWS_THRESHOLD = 200;

const RecentFeedback: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<RecentFeedbackData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);

  let parsedOutput: RecentFeedbackData = {};
  try {
    parsedOutput =
      typeof props.output === "string"
        ? (parseOutputString(props.output) as RecentFeedbackData)
        : ((props.output || {}) as RecentFeedbackData);
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
          setLoadedOutput(parseOutputString(text) as RecentFeedbackData);
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
  const title =
    props.name && !props.name.startsWith("block_")
      ? props.name
      : output.block_title || "Recent Feedback";

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
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Feedback Items</div>
            <div className="text-xl font-semibold">{summary?.total_feedback_items ?? 0}</div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Corrected</div>
            <div className="text-xl font-semibold">{summary?.corrected_feedback_items ?? 0}</div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Distinct Items</div>
            <div className="text-xl font-semibold">{summary?.distinct_items_count ?? 0}</div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Distinct Scores</div>
            <div className="text-xl font-semibold">{summary?.distinct_score_count ?? 0}</div>
          </div>
        </div>

        <div className="text-sm text-muted-foreground">
          {output.scorecard_name ? `Scorecard: ${output.scorecard_name}` : null}
          {output.score_name ? ` • Score: ${output.score_name}` : null}
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
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="bg-muted/40">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Edited At</th>
                    <th className="px-3 py-2 text-left font-medium">Item</th>
                    <th className="px-3 py-2 text-left font-medium">Score</th>
                    <th className="px-3 py-2 text-right font-medium">Initial</th>
                    <th className="px-3 py-2 text-right font-medium">Final</th>
                    <th className="px-3 py-2 text-right font-medium">Corrected</th>
                    <th className="px-3 py-2 text-right font-medium">Invalid</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                        No feedback items matched the requested filters.
                      </td>
                    </tr>
                  ) : (
                    visibleRows.map((item) => (
                      <tr key={item.feedback_item_id} className="border-t">
                        <td className="px-3 py-2 whitespace-nowrap">
                          {item.edited_at ? new Date(item.edited_at).toLocaleString() : "N/A"}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs">{item.item_id}</td>
                        <td className="px-3 py-2">
                          {item.score_name || <span className="font-mono text-xs">{item.score_id}</span>}
                        </td>
                        <td className="px-3 py-2 text-right">{item.initial_value ?? "N/A"}</td>
                        <td className="px-3 py-2 text-right">{item.final_value ?? "N/A"}</td>
                        <td className="px-3 py-2 text-right">{item.corrected ? "Yes" : "No"}</td>
                        <td className="px-3 py-2 text-right">{item.is_invalid ? "Yes" : "No"}</td>
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

export default RecentFeedback;

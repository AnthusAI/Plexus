"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";

import { parseOutputString } from "@/lib/utils";
import ReportBlock, { ReportBlockProps } from "./ReportBlock";

interface OverturnSummary {
  total_items: number;
  total_score_results: number;
  overturned_score_results: number;
  upheld_score_results: number;
  corpus_overturn_rate: number;
}

interface OverturnItem {
  item_id: string;
  total_score_results: number;
  overturned_score_results: number;
  upheld_score_results: number;
  overturn_rate: number;
}

interface OverturnRateData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
  scorecard_name?: string;
  score_name?: string | null;
  date_range?: {
    start: string;
    end: string;
  };
  summary?: OverturnSummary;
  items?: OverturnItem[];
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

const OverturnRate: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<OverturnRateData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);

  let parsedOutput: OverturnRateData = {};
  try {
    parsedOutput =
      typeof props.output === "string"
        ? (parseOutputString(props.output) as OverturnRateData)
        : ((props.output || {}) as OverturnRateData);
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
          setLoadedOutput(parseOutputString(text) as OverturnRateData);
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
  const title =
    props.name && !props.name.startsWith("block_")
      ? props.name
      : output.block_title || "Overturn Rate";

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
            <div className="text-xs text-muted-foreground">Corpus Overturn Rate</div>
            <div className="text-xl font-semibold">
              {formatPercent(summary?.corpus_overturn_rate)}
            </div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Items</div>
            <div className="text-xl font-semibold">{summary?.total_items ?? 0}</div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Overturned Score Results</div>
            <div className="text-xl font-semibold">{summary?.overturned_score_results ?? 0}</div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Total Score Results</div>
            <div className="text-xl font-semibold">{summary?.total_score_results ?? 0}</div>
          </div>
        </div>

        <div className="text-sm text-muted-foreground">
          {output.scorecard_name ? `Scorecard: ${output.scorecard_name}` : null}
          {output.score_name ? ` • Score: ${output.score_name}` : null}
        </div>

        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Item</th>
                <th className="px-3 py-2 text-right font-medium">Score Results</th>
                <th className="px-3 py-2 text-right font-medium">Overturned</th>
                <th className="px-3 py-2 text-right font-medium">Upheld</th>
                <th className="px-3 py-2 text-right font-medium">Overturn Rate</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                    No score results matched the requested filters.
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.item_id} className="border-t">
                    <td className="px-3 py-2 font-mono text-xs">{item.item_id}</td>
                    <td className="px-3 py-2 text-right">{item.total_score_results}</td>
                    <td className="px-3 py-2 text-right">{item.overturned_score_results}</td>
                    <td className="px-3 py-2 text-right">{item.upheld_score_results}</td>
                    <td className="px-3 py-2 text-right">{formatPercent(item.overturn_rate)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </ReportBlock>
  );
};

export default OverturnRate;

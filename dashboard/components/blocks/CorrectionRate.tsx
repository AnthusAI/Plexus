"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";

import { parseOutputString } from "@/lib/utils";
import ReportBlock, { ReportBlockProps } from "./ReportBlock";

interface CorrectionSummary {
  total_items: number;
  total_score_results: number;
  corrected_score_results: number;
  uncorrected_score_results: number;
  corpus_correction_rate: number;
}

interface CorrectionItem {
  item_id: string;
  total_score_results: number;
  corrected_score_results: number;
  uncorrected_score_results: number;
  correction_rate: number;
}

interface CorrectionRateData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
  scorecard_name?: string;
  score_name?: string | null;
  date_range?: {
    start: string;
    end: string;
  };
  summary?: CorrectionSummary;
  items?: CorrectionItem[];
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

const CorrectionRate: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<CorrectionRateData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);

  let parsedOutput: CorrectionRateData = {};
  try {
    parsedOutput =
      typeof props.output === "string"
        ? (parseOutputString(props.output) as CorrectionRateData)
        : ((props.output || {}) as CorrectionRateData);
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
          setLoadedOutput(parseOutputString(text) as CorrectionRateData);
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
      : output.block_title || "Correction Rate";

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
            <div className="text-xs text-muted-foreground">Corpus Correction Rate</div>
            <div className="text-xl font-semibold">
              {formatPercent(summary?.corpus_correction_rate)}
            </div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Items</div>
            <div className="text-xl font-semibold">{summary?.total_items ?? 0}</div>
          </div>
          <div className="rounded-md border p-3">
            <div className="text-xs text-muted-foreground">Corrected Score Results</div>
            <div className="text-xl font-semibold">{summary?.corrected_score_results ?? 0}</div>
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
                <th className="px-3 py-2 text-right font-medium">Corrected</th>
                <th className="px-3 py-2 text-right font-medium">Uncorrected</th>
                <th className="px-3 py-2 text-right font-medium">Correction Rate</th>
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
                    <td className="px-3 py-2 text-right">{item.corrected_score_results}</td>
                    <td className="px-3 py-2 text-right">{item.uncorrected_score_results}</td>
                    <td className="px-3 py-2 text-right">{formatPercent(item.correction_rate)}</td>
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

export default CorrectionRate;

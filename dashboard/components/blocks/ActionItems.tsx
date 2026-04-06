"use client";

import React, { useState } from "react";
import { ReportBlockProps, BlockComponent } from "./ReportBlock";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, MessageSquareCode, Copy } from "lucide-react";
import { parseOutputString } from "@/lib/utils";
import { toast } from "sonner";
import { type IdentifierItem } from "@/components/ui/identifier-display";

interface Exemplar {
  text: string;
  item_id?: string;
  initial_answer_value?: string;
  final_answer_value?: string;
  score_explanation?: string | null;
  identifiers?: IdentifierItem[];
}

interface ActionItem {
  scorecard_name: string;
  score_name: string;
  score_ac1: number | null;
  score_mismatches: number;
  topic_label: string;
  cause?: string;
  keywords?: string[];
  member_count: number;
  days_inactive: number;
  lifecycle_tier?: string;
  is_new: boolean;
  is_trending: boolean;
  exemplars: Exemplar[];
}

interface ActionItemsData {
  action_items?: ActionItem[];
  total_count?: number;
  date_range?: { start?: string; end?: string };
  thresholds?: { ac1_threshold?: number; recency_days?: number };
  generated_at?: string;
  status?: string;
  message?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

function CodePanel({ json, onCopy }: { json: string; onCopy: () => void }) {
  return (
    <div className="mt-2 bg-card rounded-lg p-3">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">JSON</span>
        <Button variant="ghost" size="sm" className="h-6 px-2" onClick={onCopy}>
          <Copy className="w-3 h-3 mr-1" />
          <span className="text-xs">Copy</span>
        </Button>
      </div>
      <pre className="whitespace-pre-wrap text-xs font-mono text-foreground overflow-y-auto max-h-64 overflow-x-auto">
        {json}
      </pre>
    </div>
  );
}

function ExemplarRow({ ex }: { ex: Exemplar }) {
  const url = ex.identifiers?.find(id => id.url)?.url;
  return (
    <div className="border-l-2 border-muted pl-3 py-1 text-sm space-y-0.5">
      <p className="text-foreground">{ex.text}</p>
      {(ex.initial_answer_value || ex.final_answer_value) && (
        <p className="text-muted-foreground text-xs">
          Original: <span className="font-medium">{ex.initial_answer_value ?? "—"}</span>
          {" → "}
          Corrected: <span className="font-medium">{ex.final_answer_value ?? "—"}</span>
        </p>
      )}
      <p className="text-muted-foreground text-xs italic">
        AI reasoning: {ex.score_explanation || <span className="opacity-50">not available</span>}
      </p>
      {url && (
        <a href={url} target="_blank" rel="noopener noreferrer"
           className="text-xs text-primary hover:underline">{url}</a>
      )}
    </div>
  );
}

function ActionItemCard({ item }: { item: ActionItem }) {
  const [expanded, setExpanded] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const ac1Display = item.score_ac1 != null ? item.score_ac1.toFixed(3) : "—";
  const itemJson = JSON.stringify(item, null, 2);

  const copyItemCode = async () => {
    try {
      await navigator.clipboard.writeText(itemJson);
      toast.success("Action item copied to clipboard");
    } catch {
      toast.error("Failed to copy to clipboard");
    }
  };

  return (
    <div className="rounded-lg bg-muted/20 overflow-hidden">
      <div className="bg-muted/30 px-4 py-3 flex items-start justify-between gap-2">
        <button
          className="flex-1 text-left min-w-0"
          onClick={() => setExpanded(v => !v)}
        >
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="font-medium text-sm">{item.score_name}</span>
            <span className="text-muted-foreground text-sm">›</span>
            <span className="text-sm">{item.topic_label}</span>
            {item.lifecycle_tier === "new" && (
              <Badge variant="secondary" className="text-xs border-0 bg-blue-500/15 text-blue-700 dark:text-blue-400">
                NEW
              </Badge>
            )}
            {item.lifecycle_tier === "trending" && (
              <Badge variant="secondary" className="text-xs border-0 bg-amber-500/15 text-amber-700 dark:text-amber-400">
                TRENDING
              </Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
            <span>AC1: {ac1Display}</span>
            <span>{item.member_count} item{item.member_count !== 1 ? "s" : ""}</span>
            <span>{item.days_inactive}d ago</span>
          </div>
        </button>
        <div className="flex items-center gap-1 flex-shrink-0 mt-0.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={() => setShowCode(v => !v)}
            title="Show code"
          >
            <MessageSquareCode className="w-3.5 h-3.5 text-muted-foreground" />
          </Button>
          <button onClick={() => setExpanded(v => !v)}>
            {expanded
              ? <ChevronDown className="w-4 h-4 text-muted-foreground" />
              : <ChevronRight className="w-4 h-4 text-muted-foreground" />
            }
          </button>
        </div>
      </div>

      {(expanded || showCode) && (
        <div className="px-4 py-3 space-y-3">
          {showCode && <CodePanel json={itemJson} onCopy={copyItemCode} />}
          {item.cause && (
            <p className="text-sm">
              <span className="font-medium">Root cause: </span>{item.cause}
            </p>
          )}
          {item.keywords && item.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {item.keywords.map((kw, i) => (
                <Badge key={i} variant="secondary" className="text-xs border-0 bg-muted/50">{kw}</Badge>
              ))}
            </div>
          )}
          {item.exemplars.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Examples</p>
              {item.exemplars.map((ex, i) => <ExemplarRow key={i} ex={ex} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const ActionItems: React.FC<ReportBlockProps> = ({ output, name }) => {
  const [loadedOutput, setLoadedOutput] = React.useState<ActionItemsData | null>(null);
  const [showBlockCode, setShowBlockCode] = React.useState(false);

  let parsedOutput: ActionItemsData = {};
  try {
    parsedOutput = typeof output === "string"
      ? (parseOutputString(output) as ActionItemsData)
      : ((output || {}) as ActionItemsData);
  } catch {
    parsedOutput = {};
  }

  React.useEffect(() => {
    if (!parsedOutput.output_compacted || !parsedOutput.output_attachment || loadedOutput) {
      return;
    }
    (async () => {
      try {
        const { downloadData } = await import("aws-amplify/storage");
        const result = await downloadData({
          path: parsedOutput.output_attachment!,
          options: { bucket: "reportBlockDetails" as any },
        }).result;
        const text = await result.body.text();
        setLoadedOutput(parseOutputString(text) as ActionItemsData);
      } catch (error) {
        console.warn("ActionItems: failed to load compacted output attachment", error);
      }
    })();
  }, [loadedOutput, parsedOutput.output_attachment, parsedOutput.output_compacted]);

  const data = loadedOutput ?? parsedOutput;
  const items = data.action_items ?? [];
  const thresholds = data.thresholds ?? {};

  const subtitleParts: string[] = [];
  if (thresholds.ac1_threshold != null) subtitleParts.push(`AC1 < ${thresholds.ac1_threshold}`);
  if (thresholds.recency_days != null) subtitleParts.push(`last ${thresholds.recency_days} days`);

  const blockJson = JSON.stringify(data, null, 2);
  const copyBlockCode = async () => {
    try {
      await navigator.clipboard.writeText(blockJson);
      toast.success("Action items copied to clipboard");
    } catch {
      toast.error("Failed to copy to clipboard");
    }
  };

  // Group by scorecard
  const byScorecardMap = new Map<string, ActionItem[]>();
  for (const item of items) {
    const sc = item.scorecard_name || "Unknown";
    if (!byScorecardMap.has(sc)) byScorecardMap.set(sc, []);
    byScorecardMap.get(sc)!.push(item);
  }
  const scorecards = Array.from(byScorecardMap.entries());

  return (
    <Card className="border-0 shadow-none bg-transparent">
      <CardHeader className="px-0 pt-0">
        <div className="flex items-start justify-between gap-2">
          <CardTitle>{name || "Action Items"}</CardTitle>
          {(loadedOutput || !parsedOutput.output_compacted) && items.length > 0 && (
            <Button
              variant="secondary"
              size="sm"
              className="h-8 bg-card hover:bg-card/90 border-0 flex-shrink-0"
              onClick={() => setShowBlockCode(v => !v)}
            >
              <MessageSquareCode className="w-4 h-4 mr-2" />
              {showBlockCode ? "Hide Code" : "Code"}
            </Button>
          )}
        </div>
        {subtitleParts.length > 0 && (
          <p className="text-sm text-muted-foreground mt-1">
            Significant errors requiring attention — {subtitleParts.join(", ")}
          </p>
        )}
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">
            {items.length} action item{items.length !== 1 ? "s" : ""}
          </Badge>
          {data.date_range?.start && data.date_range?.end && (
            <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">
              {data.date_range.start} – {data.date_range.end}
            </Badge>
          )}
        </div>
        {showBlockCode && <CodePanel json={blockJson} onCopy={copyBlockCode} />}
      </CardHeader>
      <CardContent className="px-0 pb-0 space-y-6">
        {parsedOutput.output_compacted && !loadedOutput ? (
          <p className="text-sm text-muted-foreground italic">Loading action items…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">
            {data.message || "No significant action items found in the specified date range."}
          </p>
        ) : (
          scorecards.map(([scName, scItems]) => (
            <div key={scName}>
              {scorecards.length > 1 && (
                <h3 className="font-semibold text-base mb-3">{scName}</h3>
              )}
              <div className="space-y-2">
                {scItems.map((item, i) => <ActionItemCard key={i} item={item} />)}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
};

(ActionItems as BlockComponent).blockClass = "ActionItems";

export default ActionItems;

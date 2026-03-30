"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { IdentifierDisplay } from "@/components/ui/identifier-display";
import { LabelBadgeComparison } from "@/components/LabelBadgeComparison";

export interface TopicExemplar {
  text: string;
  item_id?: string | null;
  identifiers?: Array<{ name: string; value: string; url?: string }> | null;
  initial_answer_value?: string | null;
  final_answer_value?: string | null;
  score_explanation?: string | null;
  above_fold?: boolean;
  timestamp?: string | null;
  detailed_cause?: string | null;
}

export interface Topic {
  topic_id?: number;
  cluster_id?: number;
  label: string;
  keywords?: string[];
  exemplars?: Array<TopicExemplar | string>;
  memory_weight: number;
  memory_tier: string;
  lifecycle_tier?: string;
  cause?: string;
  detailed_explanation?: string;
  improvement_suggestion?: string;
  is_new?: boolean;
  is_trending?: boolean;
  has_short_term_memory?: boolean;
  has_medium_term_memory?: boolean;
  has_long_term_memory?: boolean;
  p95_distance?: number;
  member_count: number;
  days_inactive?: number;
}

interface TopicItemProps {
  topic: Topic;
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 30) return `${diffDays}d ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
}

function TopicItem({ topic }: TopicItemProps) {
  const [expanded, setExpanded] = useState(false);
  const [showBelowFold, setShowBelowFold] = useState(false);
  const hasDetails =
    (topic.keywords?.length ?? 0) > 0 ||
    (topic.exemplars?.length ?? 0) > 0 ||
    topic.days_inactive !== undefined ||
    !!topic.cause ||
    !!topic.detailed_explanation ||
    !!topic.improvement_suggestion;

  const allExemplars = (topic.exemplars ?? []).filter((ex): ex is TopicExemplar => typeof ex !== "string" || ex !== "");
  const aboveFoldExemplars = allExemplars.filter((ex) =>
    typeof ex === "string" ? true : (ex.above_fold !== false)
  );
  const belowFoldExemplars = allExemplars.filter((ex) =>
    typeof ex !== "string" && ex.above_fold === false
  );

  return (
    <li className="pb-3">
      <button
        type="button"
        onClick={() => hasDetails && setExpanded((e) => !e)}
        className="w-full flex items-center justify-between py-2 text-left hover:bg-muted/30 rounded px-2 -mx-2"
      >
        <div className="flex items-center gap-2 min-w-0">
          {hasDetails ? (
            expanded ? (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            )
          ) : null}
          <span className="font-medium truncate">{topic.label}</span>
        </div>
        <div className="flex gap-2 text-sm text-muted-foreground shrink-0 ml-2">
          {topic.days_inactive !== undefined && (
            <Badge variant="secondary" className="font-mono text-xs bg-muted/50 hover:bg-muted/50 border-0">
              {topic.days_inactive}d inactive
            </Badge>
          )}
          {topic.lifecycle_tier && (
            <Badge
              variant={topic.lifecycle_tier === "new" ? "default" : "secondary"}
              className={topic.lifecycle_tier !== "new" ? "bg-muted/50 hover:bg-muted/50 border-0" : "border-0"}
            >
              {topic.lifecycle_tier}
            </Badge>
          )}
          <Badge
            variant={topic.memory_tier === "hot" ? "default" : "secondary"}
            className={topic.memory_tier === "warm" ? "bg-muted/50 hover:bg-muted/50 border-0" : "border-0"}
          >
            {topic.memory_tier}
          </Badge>
          <span>
            {topic.member_count} item{topic.member_count !== 1 ? "s" : ""}
          </span>
        </div>
      </button>
      {expanded && hasDetails && (
        <div className="pl-6 pr-2 space-y-3 text-sm">
          {topic.detailed_explanation && (
            <div>
              <div className="font-medium text-muted-foreground mb-1">Analysis</div>
              <div className="text-foreground whitespace-pre-line">{topic.detailed_explanation}</div>
            </div>
          )}
          {topic.improvement_suggestion && (
            <div>
              <div className="font-medium text-muted-foreground mb-1">Suggested Improvement</div>
              <div className="text-foreground whitespace-pre-line">{topic.improvement_suggestion}</div>
            </div>
          )}
          {!topic.detailed_explanation && topic.cause && (
            <div>
              <span className="font-medium text-muted-foreground">Root cause: </span>
              <span className="text-foreground">{topic.cause}</span>
            </div>
          )}
          {topic.keywords && topic.keywords.length > 0 && (
            <div>
              <span className="font-medium text-muted-foreground">Keywords: </span>
              <span className="text-foreground">{topic.keywords.join(", ")}</span>
            </div>
          )}
          {allExemplars.length > 0 && (
            <div>
              <div className="font-medium text-muted-foreground mb-1">Exemplars</div>
              <ul className="space-y-2 list-disc list-inside">
                {aboveFoldExemplars.map((ex, i) => {
                  if (typeof ex === "string") {
                    return (
                      <li key={i} className="text-muted-foreground italic">
                        &quot;{ex}&quot;
                      </li>
                    );
                  }
                  return (
                    <li key={i} className="text-muted-foreground flex flex-col gap-0.5">
                      <div className="flex items-start justify-between gap-2">
                        <span className="italic">&quot;{ex.text}&quot;</span>
                        {ex.timestamp && (
                          <span className="text-xs text-muted-foreground/60 shrink-0 mt-0.5">
                            {formatTimestamp(ex.timestamp)}
                          </span>
                        )}
                      </div>
                      {(ex.initial_answer_value || ex.final_answer_value) && (
                        <LabelBadgeComparison
                          predictedLabel={ex.initial_answer_value ?? "—"}
                          actualLabel={ex.final_answer_value ?? "—"}
                          isCorrect={ex.initial_answer_value === ex.final_answer_value}
                          showStatus={false}
                        />
                      )}
                      {ex.detailed_cause && (
                        <span className="text-xs text-foreground/80 italic">Analysis: {ex.detailed_cause}</span>
                      )}
                      {ex.score_explanation && (
                        <span className="text-xs italic">AI reasoning: {ex.score_explanation}</span>
                      )}
                      {(ex.item_id || ex.identifiers?.length) && (
                        <div className="shrink-0">
                          <IdentifierDisplay
                            externalId={ex.item_id ?? undefined}
                            identifiers={ex.identifiers ?? undefined}
                            displayMode="full"
                          />
                        </div>
                      )}
                    </li>
                  );
                })}
                {belowFoldExemplars.length > 0 && !showBelowFold && (
                  <li className="list-none">
                    <button
                      type="button"
                      onClick={() => setShowBelowFold(true)}
                      className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2"
                    >
                      Show {belowFoldExemplars.length} more example{belowFoldExemplars.length !== 1 ? "s" : ""}
                    </button>
                  </li>
                )}
                {showBelowFold && belowFoldExemplars.map((ex, i) => (
                  <li key={`below-${i}`} className="text-muted-foreground flex flex-col gap-0.5">
                    <div className="flex items-start justify-between gap-2">
                      <span className="italic">&quot;{ex.text}&quot;</span>
                      {ex.timestamp && (
                        <span className="text-xs text-muted-foreground/60 shrink-0 mt-0.5">
                          {formatTimestamp(ex.timestamp)}
                        </span>
                      )}
                    </div>
                    {(ex.initial_answer_value || ex.final_answer_value) && (
                      <LabelBadgeComparison
                        predictedLabel={ex.initial_answer_value ?? "—"}
                        actualLabel={ex.final_answer_value ?? "—"}
                        isCorrect={ex.initial_answer_value === ex.final_answer_value}
                        showStatus={false}
                      />
                    )}
                    {ex.score_explanation && (
                      <span className="text-xs italic">AI reasoning: {ex.score_explanation}</span>
                    )}
                    {(ex.item_id || ex.identifiers?.length) && (
                      <div className="shrink-0">
                        <IdentifierDisplay
                          externalId={ex.item_id ?? undefined}
                          identifiers={ex.identifiers ?? undefined}
                          displayMode="full"
                        />
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export interface TopicListProps {
  topics: Topic[];
  label?: string;
}

/**
 * Renders a labeled list of topics with keywords, memory tiers, and expandable exemplars.
 * Exemplars support enriched objects with item_id and identifiers (rendered via IdentifierDisplay)
 * as well as plain strings for backward compatibility.
 */
export function TopicList({ topics, label }: TopicListProps) {
  if (!topics || topics.length === 0) return null;

  const sorted = [...topics].sort((a, b) => {
    const aInactive = a.days_inactive ?? Infinity;
    const bInactive = b.days_inactive ?? Infinity;
    if (aInactive !== bInactive) return aInactive - bInactive;
    return b.member_count - a.member_count;
  });

  return (
    <div>
      {label && (
        <h4 className="font-medium text-sm text-muted-foreground mb-2">{label}</h4>
      )}
      <ul className="space-y-2">
        {sorted.map((t) => (
          <TopicItem key={t.topic_id ?? t.cluster_id ?? t.label} topic={t} />
        ))}
      </ul>
    </div>
  );
}

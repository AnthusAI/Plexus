"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { IdentifierDisplay } from "@/components/ui/identifier-display";

export interface TopicExemplar {
  text: string;
  item_id?: string | null;
  identifiers?: Array<{ name: string; value: string; url?: string }> | null;
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

function TopicItem({ topic }: TopicItemProps) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails =
    (topic.keywords?.length ?? 0) > 0 ||
    (topic.exemplars?.length ?? 0) > 0 ||
    topic.days_inactive !== undefined ||
    !!topic.cause;

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
          {topic.cause && (
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
          {topic.exemplars && topic.exemplars.length > 0 && (
            <div>
              <div className="font-medium text-muted-foreground mb-1">Exemplars</div>
              <ul className="space-y-2 list-disc list-inside">
                {topic.exemplars.map((ex, i) => {
                  if (typeof ex === "string") {
                    return (
                      <li key={i} className="text-muted-foreground italic">
                        &quot;{ex}&quot;
                      </li>
                    );
                  }
                  return (
                    <li key={i} className="text-muted-foreground flex items-start justify-between gap-2">
                      <span className="italic">&quot;{ex.text}&quot;</span>
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

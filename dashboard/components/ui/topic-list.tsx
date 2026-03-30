"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, MessageSquareCode } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";

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
  suggested_fix?: string | null;
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

type RcaDataByItemId = Record<string, { detailed_cause?: string; suggested_fix?: string }>

interface TopicItemProps {
  topic: Topic;
  isExpanded: boolean;
  onToggle: (topic: Topic) => void;
}

function TopicItem({ topic, isExpanded, onToggle }: TopicItemProps) {
  const [showCode, setShowCode] = useState(false);
  const hasDetails =
    (topic.keywords?.length ?? 0) > 0 ||
    (topic.exemplars?.length ?? 0) > 0 ||
    topic.days_inactive !== undefined ||
    !!topic.cause ||
    !!topic.detailed_explanation ||
    !!topic.improvement_suggestion;

  return (
    <li className="pb-3">
      <div className="flex items-center py-2 hover:bg-muted/30 rounded px-2 -mx-2">
        <button
          type="button"
          onClick={() => { if (hasDetails) onToggle(topic); }}
          className="flex-1 flex items-center justify-between text-left min-w-0"
        >
          <div className="flex items-center gap-2 min-w-0">
            {hasDetails ? (
              isExpanded ? (
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
        {isExpanded && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 ml-1 shrink-0"
            onClick={(e) => { e.stopPropagation(); setShowCode(v => !v); }}
            title="Show JSON"
          >
            <MessageSquareCode className="w-3.5 h-3.5 text-muted-foreground" />
          </Button>
        )}
      </div>
      {isExpanded && hasDetails && (
        <div className="pl-6 pr-2 space-y-3 text-sm">
          {showCode ? (
            <pre className="whitespace-pre-wrap text-xs font-mono text-foreground bg-background rounded-md p-3 overflow-y-auto max-h-96 overflow-x-auto">
              {JSON.stringify(topic, null, 2)}
            </pre>
          ) : (
            <>
              {topic.detailed_explanation && (
                <div>
                  <div className="font-medium text-muted-foreground mb-1">Analysis</div>
                  <div className="prose prose-sm max-w-none prose-p:text-foreground prose-strong:text-foreground prose-headings:text-foreground prose-li:text-foreground">
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={{
                      p: ({children}) => <p className="mb-2 last:mb-0 text-sm">{children}</p>,
                      ul: ({children}) => <ul className="mb-2 ml-4 list-disc">{children}</ul>,
                      ol: ({children}) => <ol className="mb-2 ml-4 list-decimal">{children}</ol>,
                      li: ({children}) => <li className="mb-1">{children}</li>,
                      strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                    }}>{topic.detailed_explanation}</ReactMarkdown>
                  </div>
                </div>
              )}
              {topic.improvement_suggestion && (
                <div>
                  <div className="font-medium text-muted-foreground mb-1">Suggested Improvement</div>
                  <div className="prose prose-sm max-w-none prose-p:text-foreground prose-strong:text-foreground prose-headings:text-foreground prose-li:text-foreground">
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={{
                      p: ({children}) => <p className="mb-2 last:mb-0 text-sm">{children}</p>,
                      ul: ({children}) => <ul className="mb-2 ml-4 list-disc">{children}</ul>,
                      ol: ({children}) => <ol className="mb-2 ml-4 list-decimal">{children}</ol>,
                      li: ({children}) => <li className="mb-1">{children}</li>,
                      strong: ({children}) => <strong className="font-semibold">{children}</strong>,
                    }}>{topic.improvement_suggestion}</ReactMarkdown>
                  </div>
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
            </>
          )}
        </div>
      )}
    </li>
  );
}

export interface TopicListProps {
  topics: Topic[];
  label?: string;
  onTopicFilter?: (itemIds: string[] | null, rcaDataByItemId: RcaDataByItemId) => void;
}

/**
 * Renders a labeled list of topics with keywords, memory tiers, and expandable analysis.
 * When a topic is expanded, onTopicFilter is called with the topic's exemplar item IDs
 * so the parent can filter the score results list to show only that topic's items.
 */
export function TopicList({ topics, label, onTopicFilter }: TopicListProps) {
  const [expandedKey, setExpandedKey] = useState<string | number | null>(null);

  if (!topics || topics.length === 0) return null;

  const sorted = [...topics].sort((a, b) => {
    const aInactive = a.days_inactive ?? Infinity;
    const bInactive = b.days_inactive ?? Infinity;
    if (aInactive !== bInactive) return aInactive - bInactive;
    return b.member_count - a.member_count;
  });

  const handleToggle = (topic: Topic) => {
    const key = topic.topic_id ?? topic.cluster_id ?? topic.label;
    const isCurrentlyExpanded = expandedKey === key;
    const next = isCurrentlyExpanded ? null : key;
    setExpandedKey(next);

    if (onTopicFilter) {
      if (next !== null) {
        const exemplars = (topic.exemplars ?? []).filter(
          (ex): ex is TopicExemplar => typeof ex !== "string"
        );
        const itemIds = exemplars
          .map((ex) => ex.item_id)
          .filter((id): id is string => !!id);
        const rcaDataByItemId: RcaDataByItemId = {};
        exemplars.forEach((ex) => {
          if (ex.item_id) {
            rcaDataByItemId[ex.item_id] = {
              detailed_cause: ex.detailed_cause ?? undefined,
              suggested_fix: ex.suggested_fix ?? undefined,
            };
          }
        });
        onTopicFilter(itemIds, rcaDataByItemId);
      } else {
        onTopicFilter(null, {});
      }
    }
  };

  return (
    <div>
      {label && (
        <h4 className="font-medium text-sm text-muted-foreground mb-2">{label}</h4>
      )}
      <ul className="space-y-2">
        {sorted.map((t) => {
          const key = t.topic_id ?? t.cluster_id ?? t.label;
          return (
            <TopicItem
              key={key}
              topic={t}
              isExpanded={expandedKey === key}
              onToggle={handleToggle}
            />
          );
        })}
      </ul>
    </div>
  );
}

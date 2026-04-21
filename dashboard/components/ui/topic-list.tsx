"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, MessageSquareCode } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
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
  misclassification_classification?: {
    primary_category?: string;
    rationale?: string;
    confidence?: string;
    evidence_snippets?: Array<{
      source?: string;
      quote_or_fact?: string;
    }>;
  };
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
  isExpanded: boolean;
  onToggle: (topic: Topic) => void;
  onViewItems?: (topic: Topic) => void;
  onClearTopicFilter?: () => void;
  isTopicFiltered?: boolean;
  topicCategoryInfo?: {
    primaryCategory?: string;
    purity?: number;
    categoryCounts?: Record<string, number>;
  };
}

const getCategoryLabel = (category?: string | null): string => {
  switch (category) {
    case "score_configuration_problem":
      return "Score configuration"
    case "information_gap":
      return "Information gap"
    case "guideline_gap_requires_sme":
      return "SME guideline gap"
    case "mechanical_malfunction":
      return "Mechanical malfunction"
    default:
      return category ? category.replace(/_/g, " ") : "Unclassified"
  }
}

const getCategoryBadgeClass = (category?: string | null): string => {
  switch (category) {
    case "score_configuration_problem":
      return "bg-chart-1/20 text-chart-1"
    case "information_gap":
      return "bg-chart-2/20 text-chart-2"
    case "guideline_gap_requires_sme":
      return "bg-chart-3/20 text-chart-3"
    case "mechanical_malfunction":
      return "bg-chart-4/20 text-chart-4"
    default:
      return "bg-muted text-muted-foreground"
  }
}

const containsLuaTablePointer = (value: unknown): boolean => {
  if (typeof value !== "string") return false;
  return value.toLowerCase().includes("<lua table at ");
};

const normalizeTopicText = (value: unknown): string | null => {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (containsLuaTablePointer(trimmed)) return null;
  return trimmed;
};

function getTopicItemIds(topic: Topic): string[] {
  const exemplars = (topic.exemplars ?? []).filter(
    (ex): ex is TopicExemplar => typeof ex !== "string"
  );
  return exemplars
    .map((ex) => ex.item_id)
    .filter((id): id is string => !!id);
}

function TopicItem({
  topic,
  isExpanded,
  onToggle,
  onViewItems,
  onClearTopicFilter,
  isTopicFiltered,
  topicCategoryInfo,
}: TopicItemProps) {
  const [showCode, setShowCode] = useState(false);
  const topicLabel = normalizeTopicText(topic.label) ?? "Unlabeled topic";
  const topicCause = normalizeTopicText(topic.cause);
  const topicItemIds = getTopicItemIds(topic);
  const hasDetails =
    (topic.keywords?.length ?? 0) > 0 ||
    (topic.exemplars?.length ?? 0) > 0 ||
    topic.days_inactive !== undefined ||
    !!topicCause ||
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
            <span className="font-medium truncate">{topicLabel}</span>
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
            {topicCategoryInfo?.primaryCategory && (
              <Badge
                variant="secondary"
                className={`border-0 ${getCategoryBadgeClass(topicCategoryInfo.primaryCategory)}`}
              >
                {getCategoryLabel(topicCategoryInfo.primaryCategory)}
                {typeof topicCategoryInfo.purity === "number"
                  ? ` (${Math.round(topicCategoryInfo.purity * 100)}%)`
                  : ""}
              </Badge>
            )}
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
              {!topic.detailed_explanation && topicCause && (
                <div>
                  <span className="font-medium text-muted-foreground">Root cause: </span>
                  <span className="text-foreground">{topicCause}</span>
                </div>
              )}
              {topic.keywords && topic.keywords.length > 0 && (
                <div>
                  <span className="font-medium text-muted-foreground">Keywords: </span>
                  <span className="text-foreground">{topic.keywords.join(", ")}</span>
                </div>
              )}
              {(onViewItems && topicItemIds.length > 0) && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className={cn(
                      "h-7 text-xs border-0 shadow-none px-2",
                      isTopicFiltered
                        ? "bg-secondary text-secondary-foreground hover:bg-secondary/90"
                        : "bg-muted text-foreground hover:bg-muted/80"
                    )}
                    onClick={() => onViewItems(topic)}
                  >
                    View items ({topicItemIds.length})
                  </Button>
                  {isTopicFiltered && onClearTopicFilter && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs px-2"
                      onClick={onClearTopicFilter}
                    >
                      Clear topic filter
                    </Button>
                  )}
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
  topicCategoryInfoByKey?: Record<string, {
    primaryCategory?: string;
    purity?: number;
    categoryCounts?: Record<string, number>;
  }>;
  onTopicFilter?: (
    itemIds: string[] | null,
    topicLabel?: string | null
  ) => void;
  activeTopicLabel?: string | null;
}

/**
 * Renders a labeled list of topics with keywords, memory tiers, and expandable analysis.
 * Expanding a topic only expands details. Filtering to score results is an explicit action.
 */
export function TopicList({ topics, label, topicCategoryInfoByKey, onTopicFilter, activeTopicLabel }: TopicListProps) {
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
  };

  const handleViewItems = (topic: Topic) => {
    if (!onTopicFilter) return;
    onTopicFilter(getTopicItemIds(topic), normalizeTopicText(topic.label) ?? "Unlabeled topic");
  };

  const handleClearTopicFilter = () => {
    if (!onTopicFilter) return;
    onTopicFilter(null, null);
  };

  return (
    <div>
      {label && (
        <h4 className="font-medium text-sm text-muted-foreground mb-2">{label}</h4>
      )}
      <ul className="space-y-2">
        {sorted.map((t) => {
          const key = t.topic_id ?? t.cluster_id ?? t.label;
          const normalizedLabel = normalizeTopicText(t.label) ?? "Unlabeled topic";
          return (
            <TopicItem
              key={key}
              topic={t}
              isExpanded={expandedKey === key}
              onToggle={handleToggle}
              onViewItems={onTopicFilter ? handleViewItems : undefined}
              onClearTopicFilter={onTopicFilter ? handleClearTopicFilter : undefined}
              isTopicFiltered={Boolean(activeTopicLabel && activeTopicLabel === normalizedLabel)}
              topicCategoryInfo={topicCategoryInfoByKey?.[String(key)]}
            />
          );
        })}
      </ul>
    </div>
  );
}

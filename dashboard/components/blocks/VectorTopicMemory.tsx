"use client";

import React, { useState } from "react";
import { ReportBlockProps, BlockComponent } from "./ReportBlock";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight } from "lucide-react";
import { parseOutputString } from "@/lib/utils";

interface Topic {
  cluster_id: number;
  label: string;
  keywords?: string[];
  exemplars?: string[];
  memory_weight: number;
  memory_tier: string;
  p95_distance: number;
  member_count: number;
  days_inactive?: number;
}

interface ScoreData {
  score_id: string;
  score_name: string;
  topics: Topic[];
  items_processed: number;
  cluster_version?: string;
}

interface VectorTopicMemoryData {
  type?: string;
  status?: string;
  message?: string;
  cluster_version?: string;
  topics?: Topic[];
  scores?: ScoreData[];
  summary?: string;
  items_processed?: number;
  cache_hit_rate?: number;
  index_name?: string;
  indexed_doc_ids?: string[];
}

function TopicItem({
  topic,
}: {
  topic: Topic;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = (topic.keywords?.length ?? 0) > 0 || (topic.exemplars?.length ?? 0) > 0 || topic.days_inactive !== undefined;

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
             <Badge variant="secondary" className="font-mono text-xs bg-muted/50 hover:bg-muted/50 border-0">{topic.days_inactive}d inactive</Badge>
          )}
          <Badge variant={topic.memory_tier === 'hot' ? "default" : "secondary"} className={topic.memory_tier === 'warm' ? "bg-muted/50 hover:bg-muted/50 border-0" : "border-0"}>
            {topic.memory_tier}
          </Badge>
          <span>{topic.member_count} comment{topic.member_count !== 1 ? "s" : ""}</span>
        </div>
      </button>
      {expanded && hasDetails && (
        <div className="pl-6 pr-2 space-y-3 text-sm">
          {topic.keywords && topic.keywords.length > 0 && (
            <div>
              <span className="font-medium text-muted-foreground">Keywords: </span>
              <span className="text-foreground">
                {topic.keywords.join(", ")}
              </span>
            </div>
          )}
          {topic.exemplars && topic.exemplars.length > 0 && (
            <div>
              <div className="font-medium text-muted-foreground mb-1">Exemplars</div>
              <ul className="space-y-2 list-disc list-inside">
                {topic.exemplars.map((ex, i) => (
                  <li key={i} className="text-muted-foreground italic">
                    &quot;{ex}&quot;
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

function ScoreSection({ score }: { score: ScoreData }) {
  const hasClusters = (score.topics?.length ?? 0) > 0;
  
  return (
    <div className="rounded-lg bg-muted/20 mt-6 first:mt-0">
      <div className="bg-muted/30 px-4 py-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-base">{score.score_name}</h3>
        <div className="flex gap-2">
           <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">{score.items_processed} items</Badge>
           {hasClusters && <Badge variant="secondary" className="border-0">{score.topics.length} topics</Badge>}
        </div>
      </div>
      <div className="p-4">
        {hasClusters ? (
          <ul className="space-y-2">
            {score.topics.map((t) => (
              <TopicItem key={t.cluster_id} topic={t} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground italic text-center py-4">
            No clusters formed for this score (processed {score.items_processed} items).
          </p>
        )}
      </div>
    </div>
  );
}

const VectorTopicMemory: React.FC<ReportBlockProps> = ({
  config,
  output,
  name,
}) => {
  let data: VectorTopicMemoryData = {};
  try {
    if (typeof output === "string") {
      data = parseOutputString(output) as VectorTopicMemoryData;
    } else {
      data = (output || {}) as VectorTopicMemoryData;
    }
  } catch {
    data = {};
  }

  if (data.status === "shell" || data.status === "error") {
    return (
      <Card className="border-0 shadow-none bg-transparent">
        <CardHeader>
          <CardTitle>{name || "Vector Topic Memory"}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {data.message || data.summary || "No data available."}
          </p>
        </CardContent>
      </Card>
    );
  }

  const isMultiScore = Array.isArray(data.scores) && data.scores.length > 0;
  
  // For backwards compatibility or single-score mode
  const topicCount = data.topics?.length ?? 0;
  // Use scores for counting topics if multi-score, else use root topics length
  const hasClusters = isMultiScore ? data.scores!.some(s => s.topics?.length > 0) : topicCount > 0;

  return (
    <Card className="border-0 shadow-none bg-transparent">
      <CardHeader className="px-0 pt-0">
        <CardTitle>{name || "Vector Topic Memory"}</CardTitle>
        <p className="text-sm text-muted-foreground mt-1">
          Topics and themes from reviewer edit comments — what reviewers are saying when they correct scores.
        </p>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">{data.items_processed ?? 0} items analyzed</Badge>
          {!isMultiScore && hasClusters && (
            <Badge variant="secondary" className="border-0">{topicCount} topic{topicCount !== 1 ? "s" : ""} found</Badge>
          )}
          {isMultiScore && hasClusters && (
            <Badge variant="secondary" className="border-0">{data.scores!.reduce((acc, s) => acc + (s.topics?.length || 0), 0)} topics found</Badge>
          )}
          {data.cluster_version && (
            <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">v{data.cluster_version}</Badge>
          )}
          {data.cache_hit_rate != null && (
            <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">{Math.round(data.cache_hit_rate * 100)}% cache hit</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="px-0 pb-0 space-y-4">
        
        {isMultiScore ? (
          <div className="space-y-6">
            {data.scores!.map(score => (
              <ScoreSection key={score.score_id} score={score} />
            ))}
            
            {!hasClusters && (
              <div className="rounded-lg bg-muted/20 p-4">
                <h4 className="font-semibold mb-2">No topics formed</h4>
                <p className="text-sm text-muted-foreground">
                  Processed {data.items_processed ?? 0} items but no clusters emerged. Add more data
                  (widen the date range or include more scorecards) or lower{" "}
                  <code className="text-xs bg-muted px-1 rounded">min_topic_size</code> in the report
                  config to surface themes from smaller groups.
                </p>
                {data.index_name && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Index: <code>{data.index_name}</code>
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          /* Legacy / Single Score view */
          <>
            {hasClusters && data.topics && (
              <div className="rounded-lg bg-card p-4">
                <h4 className="font-semibold mb-3">Memories / Topics discovered</h4>
                <p className="text-sm text-muted-foreground mb-4">
                  Themes from reviewer edit comments. Each topic groups similar feedback.
                </p>
                <ul className="space-y-2">
                  {data.topics.map((t) => (
                    <TopicItem key={t.cluster_id} topic={t} />
                  ))}
                </ul>
              </div>
            )}

            {!hasClusters && (
              <div className="rounded-lg bg-muted/20 p-4">
                <h4 className="font-semibold mb-2">No topics formed</h4>
                <p className="text-sm text-muted-foreground">
                  Processed {data.items_processed ?? 0} items but no clusters emerged. Add more data
                  (widen the date range or include more scorecards) or lower{" "}
                  <code className="text-xs bg-muted px-1 rounded">min_topic_size</code> in the report
                  config to surface themes from smaller groups.
                </p>
                {data.index_name && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Index: <code>{data.index_name}</code>
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

(VectorTopicMemory as BlockComponent).blockClass = "VectorTopicMemory";

export default VectorTopicMemory;

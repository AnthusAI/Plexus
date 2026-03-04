"use client";

import React, { useState } from "react";
import { ReportBlockProps, BlockComponent } from "./ReportBlock";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight } from "lucide-react";
import { parseOutputString } from "@/lib/utils";

interface VectorTopicMemoryData {
  type?: string;
  status?: string;
  message?: string;
  cluster_version?: string;
  topics?: Array<{
    cluster_id: number;
    label: string;
    keywords?: string[];
    exemplars?: string[];
    memory_weight: number;
    memory_tier: string;
    p95_distance: number;
    member_count: number;
  }>;
  summary?: string;
  items_processed?: number;
  cache_hit_rate?: number;
  index_name?: string;
  indexed_doc_ids?: string[];
}

function TopicItem({
  topic,
}: {
  topic: {
    cluster_id: number;
    label: string;
    keywords?: string[];
    exemplars?: string[];
    member_count: number;
    memory_tier: string;
  };
}) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = (topic.keywords?.length ?? 0) > 0 || (topic.exemplars?.length ?? 0) > 0;

  return (
    <li className="border-b last:border-0 pb-3">
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
          <Badge variant="outline">{topic.memory_tier}</Badge>
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
      <Card>
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

  const topicCount = data.topics?.length ?? 0;
  const hasClusters = topicCount > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{name || "Vector Topic Memory"}</CardTitle>
        <p className="text-sm text-muted-foreground mt-1">
          Topics and themes from reviewer edit comments — what reviewers are saying when they correct scores.
        </p>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="outline">{data.items_processed ?? 0} items analyzed</Badge>
          {hasClusters && (
            <Badge variant="secondary">{topicCount} topic{topicCount !== 1 ? "s" : ""} found</Badge>
          )}
          {data.cluster_version && (
            <Badge variant="outline">v{data.cluster_version}</Badge>
          )}
          {data.cache_hit_rate != null && (
            <Badge variant="outline">{Math.round(data.cache_hit_rate * 100)}% cache hit</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Lead with memories/topics — the whole point */}
        {hasClusters && data.topics && (
          <div className="rounded-lg border bg-card p-4">
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
          <div className="rounded-lg border border-dashed bg-muted/30 p-4">
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
      </CardContent>
    </Card>
  );
};

(VectorTopicMemory as BlockComponent).blockClass = "VectorTopicMemory";

export default VectorTopicMemory;

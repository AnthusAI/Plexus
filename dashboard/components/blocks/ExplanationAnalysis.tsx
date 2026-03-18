"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TopicList, type Topic } from "@/components/ui/topic-list";
import { parseOutputString } from "@/lib/utils";
import { ReportBlockProps, type BlockComponent } from "./ReportBlock";

interface ScoreData {
  score_id: string;
  score_name: string;
  topics: Topic[];
  items_processed: number;
  cluster_version?: string;
}

interface ExplanationAnalysisData {
  type?: string;
  status?: string;
  message?: string;
  summary?: string;
  scorecard_name?: string;
  date_range?: { start: string; end: string };
  topics?: Topic[];
  scores?: ScoreData[];
  items_processed?: number;
  total_score_results_retrieved?: number;
  total_explanations_retained?: number;
  output_compacted?: boolean;
  output_attachment?: string;
}

function ScoreSection({ score }: { score: ScoreData }) {
  const hasTopics = (score.topics?.length ?? 0) > 0;

  return (
    <div className="rounded-lg bg-muted/20 mt-6 first:mt-0">
      <div className="bg-muted/30 px-4 py-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-base">{score.score_name}</h3>
        <div className="flex gap-2">
          <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">
            {score.items_processed} explanations
          </Badge>
          {hasTopics && (
            <Badge variant="secondary" className="border-0">
              {score.topics.length} topics
            </Badge>
          )}
        </div>
      </div>
      <div className="p-4">
        {hasTopics ? (
          <TopicList topics={score.topics} />
        ) : (
          <p className="text-sm text-muted-foreground italic text-center py-4">
            No topics formed for this score (processed {score.items_processed} explanations).
          </p>
        )}
      </div>
    </div>
  );
}

const ExplanationAnalysis: React.FC<ReportBlockProps> = ({ output, name }) => {
  const [loadedOutput, setLoadedOutput] = React.useState<ExplanationAnalysisData | null>(null);

  let parsedOutput: ExplanationAnalysisData = {};
  try {
    if (typeof output === "string") {
      parsedOutput = parseOutputString(output) as ExplanationAnalysisData;
    } else {
      parsedOutput = (output || {}) as ExplanationAnalysisData;
    }
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
        setLoadedOutput(parseOutputString(text) as ExplanationAnalysisData);
      } catch (error) {
        console.warn("ExplanationAnalysis: failed to load compacted output attachment", error);
      }
    })();
  }, [loadedOutput, parsedOutput.output_attachment, parsedOutput.output_compacted]);

  const data = loadedOutput ?? parsedOutput;

  if (data.status === "error") {
    return (
      <Card className="border-0 shadow-none bg-transparent">
        <CardHeader>
          <CardTitle>{name || "Explanation Analysis"}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{data.message || data.summary || "No data available."}</p>
        </CardContent>
      </Card>
    );
  }

  const scores = Array.isArray(data.scores) ? data.scores : [];
  const totalTopics = scores.reduce((sum, score) => sum + (score.topics?.length || 0), 0);

  return (
    <Card className="border-0 shadow-none bg-transparent">
      <CardHeader className="px-0 pt-0">
        <CardTitle>{name || "Explanation Analysis"}</CardTitle>
        <p className="text-sm text-muted-foreground mt-1">
          Semantic topics inferred from production ScoreResult explanations.
        </p>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">
            {data.items_processed ?? 0} explanations analyzed
          </Badge>
          <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">
            {totalTopics} topics found
          </Badge>
          {data.total_score_results_retrieved !== undefined && (
            <Badge variant="secondary" className="bg-muted/50 hover:bg-muted/50 border-0">
              {data.total_score_results_retrieved} score results scanned
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="px-0 pb-0 space-y-4">
        {data.output_compacted && !loadedOutput && (
          <div className="rounded-lg bg-muted/20 p-4 text-sm text-muted-foreground">
            Loading attached output…
          </div>
        )}

        {!data.output_compacted && scores.length === 0 && (
          <div className="rounded-lg bg-muted/20 p-4">
            <h4 className="font-semibold mb-2">No topics formed</h4>
            <p className="text-sm text-muted-foreground">
              {data.summary || "No production ScoreResult explanations were available for clustering."}
            </p>
          </div>
        )}

        {scores.length > 0 && (
          <div className="space-y-6">
            {scores.map((score) => (
              <ScoreSection key={score.score_id} score={score} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

(ExplanationAnalysis as BlockComponent).blockClass = "ExplanationAnalysis";

export default ExplanationAnalysis;

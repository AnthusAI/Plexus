"use client";

import Link from "next/link";
import { AlertCircle, ArrowLeft, Code, FileText, Terminal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import AcceptanceRate from "@/components/blocks/AcceptanceRate";
import AcceptanceRateTimeline from "@/components/blocks/AcceptanceRateTimeline";
import ActionItems from "@/components/blocks/ActionItems";
import CostAnalysis from "@/components/blocks/CostAnalysis";
import CorrectionRate from "@/components/blocks/CorrectionRate";
import ExplanationAnalysis from "@/components/blocks/ExplanationAnalysis";
import FeedbackAlignment from "@/components/blocks/FeedbackAlignment";
import FeedbackAlignmentTimeline from "@/components/blocks/FeedbackAlignmentTimeline";
import FeedbackContradictions from "@/components/blocks/FeedbackContradictions";
import FeedbackVolumeTimeline from "@/components/blocks/FeedbackVolumeTimeline";
import RecentFeedback from "@/components/blocks/RecentFeedback";
import ScoreChampionVersionTimeline from "@/components/blocks/ScoreChampionVersionTimeline";
import ScoreInfo from "@/components/blocks/ScoreInfo";
import TopicAnalysis from "@/components/blocks/TopicAnalysis";
import VectorTopicMemory from "@/components/blocks/VectorTopicMemory";

import type { ReportDoc } from "./report-docs-data";

type Props = {
  doc: ReportDoc;
};

const componentByType = {
  AcceptanceRate,
  AcceptanceRateTimeline,
  ActionItems,
  CostAnalysis,
  CorrectionRate,
  ExplanationAnalysis,
  FeedbackAlignment,
  FeedbackAlignmentTimeline,
  FeedbackContradictions,
  FeedbackVolumeTimeline,
  RecentFeedback,
  ScoreChampionVersionTimeline,
  ScoreInfo,
  TopicAnalysis,
  VectorTopicMemory,
} as const;

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-lg bg-muted p-4 text-xs">
      <code>{children}</code>
    </pre>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-2 pl-6 text-sm text-muted-foreground">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function LiveExample({ doc }: Props) {
  if (doc.relatedCheck) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Example Result</CardTitle>
          <CardDescription>This check returns a compact verdict instead of a report block.</CardDescription>
        </CardHeader>
        <CardContent>
          <CodeBlock>{`{
  "status": "potential_conflict",
  "paragraph": "The rubric says dosage does not require a separate customer repeat-back, but the score prompt still asks for explicit dosage acknowledgment.",
  "score_version_id": "abc123-version-uuid",
  "model": "gpt-5-mini"
}`}</CodeBlock>
        </CardContent>
      </Card>
    );
  }

  if (!doc.type || !doc.sampleOutput) return null;
  const Component = componentByType[doc.type as keyof typeof componentByType];
  if (!Component) return null;

  return (
    <Card className="border-2">
      <CardHeader>
        <CardTitle>Live Rendered Example</CardTitle>
        <CardDescription>Rendered with the same dashboard component used by generated reports.</CardDescription>
      </CardHeader>
      <CardContent className="border-t p-4">
        <Component
          id={`${doc.slug}-docs-example`}
          name={`${doc.title} Example`}
          type={doc.type}
          position={0}
          config={{ class: doc.type }}
          output={doc.sampleOutput}
        />
      </CardContent>
    </Card>
  );
}

export default function ReportDocPage({ doc }: Props) {
  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-8">
      <div>
        <Link href="/documentation/report-blocks" className="mb-4 inline-flex items-center gap-2 text-sm text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" />
          Back to Report Blocks
        </Link>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-bold">{doc.title}</h1>
          <Badge variant="secondary">{doc.badge}</Badge>
          {doc.relatedCheck ? <Badge variant="outline">Related check</Badge> : <Badge variant="outline">Report block</Badge>}
        </div>
        <p className="text-lg leading-relaxed text-muted-foreground">{doc.summary}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            What It Answers
          </CardTitle>
        </CardHeader>
        <CardContent>
          <BulletList items={doc.answers} />
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Use When</CardTitle>
          </CardHeader>
          <CardContent>
            <BulletList items={doc.useWhen} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Avoid When</CardTitle>
          </CardHeader>
          <CardContent>
            <BulletList items={doc.avoidWhen} />
          </CardContent>
        </Card>
      </div>

      {doc.cli ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Run From The CLI
            </CardTitle>
            <CardDescription>
              Direct report commands are the simplest path for one-off usage. Saved report configurations use `plexus report config create` and `plexus report run`.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <CodeBlock>{doc.cli}</CodeBlock>
            {doc.tactus ? (
              <CodeBlock>{doc.tactus}</CodeBlock>
            ) : null}
            {!doc.relatedCheck ? (
              <CodeBlock>{`plexus report config create --name "${doc.title} Example" --file ${doc.slug}.md
plexus report run --config "${doc.title} Example"`}</CodeBlock>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {doc.config ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Code className="h-5 w-5" />
              Minimal Configuration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CodeBlock>{doc.config}</CodeBlock>
          </CardContent>
        </Card>
      ) : null}

      <LiveExample doc={doc} />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            How To Interpret It
          </CardTitle>
        </CardHeader>
        <CardContent>
          <BulletList items={doc.interpretation} />
        </CardContent>
      </Card>
    </div>
  );
}

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { reportDocCategories, reportDocs } from "./report-docs-data";

export default function ReportBlocksPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-10 px-6 py-8">
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Report Blocks</h1>
        <p className="max-w-3xl text-lg leading-relaxed text-muted-foreground">
          Report blocks are reusable analysis components that generate metrics, charts,
          review queues, and supporting context for Plexus reports. These pages show how
          to run each report, configure it, and interpret the rendered dashboard block.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run Reports From The CLI</CardTitle>
          <CardDescription>
            Use direct feedback report commands for quick analysis, or create a saved report
            configuration when you want a reusable report template.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <pre className="overflow-x-auto rounded-lg bg-muted p-4 text-xs">
            <code>{`# Direct one-off report
plexus feedback report alignment --scorecard "Customer Service QA" --score "Medication Review: Dosage" --days 30

# Reusable report configuration
plexus report config create --name "Dosage Feedback Overview" --file dosage-report.md
plexus report run --config "Dosage Feedback Overview"`}</code>
          </pre>
          <p className="text-sm text-muted-foreground">
            `FeedbackAnalysis` is still accepted as an alias for `FeedbackAlignment`; new
            documentation uses `FeedbackAlignment`.
          </p>
        </CardContent>
      </Card>

      <div className="space-y-8">
        {reportDocCategories.map((category) => {
          const docs = reportDocs.filter((doc) => doc.category === category);
          if (docs.length === 0) return null;
          return (
            <section key={category} className="space-y-4">
              <h2 className="text-2xl font-semibold">{category}</h2>
              <div className="grid gap-4 md:grid-cols-2">
                {docs.map((doc) => (
                  <Card key={doc.slug} className="transition-shadow hover:shadow-md">
                    <CardHeader>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <CardTitle className="text-xl">
                            <Link href={`/documentation/report-blocks/${doc.slug}`} className="hover:text-primary">
                              {doc.title}
                            </Link>
                          </CardTitle>
                          <div className="mt-2 flex flex-wrap gap-2">
                            <Badge variant="secondary">{doc.badge}</Badge>
                            {doc.relatedCheck ? <Badge variant="outline">Related check</Badge> : <Badge variant="outline">Report block</Badge>}
                          </div>
                        </div>
                      </div>
                      <CardDescription className="text-base leading-relaxed">
                        {doc.summary}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div>
                        <h3 className="mb-2 text-sm font-medium">Answers</h3>
                        <ul className="space-y-1 text-sm text-muted-foreground">
                          {doc.answers.slice(0, 3).map((answer) => (
                            <li key={answer} className="flex gap-2">
                              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                              <span>{answer}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <Link href={`/documentation/report-blocks/${doc.slug}`}>
                        <Button>View Documentation</Button>
                      </Link>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          );
        })}
      </div>

      <Card className="bg-muted/50">
        <CardHeader>
          <CardTitle>Related Documentation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Link href="/documentation/concepts/reports" className="block text-primary hover:underline">
            Reports concept overview
          </Link>
          <Link href="/documentation/advanced/cli" className="block text-primary hover:underline">
            CLI command reference
          </Link>
          <Link href="/documentation/concepts/rubric-memory" className="block text-primary hover:underline">
            Rubric memory
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

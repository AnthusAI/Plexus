import { Button as DocButton } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import Link from "next/link"

const blockTypes = [
  {
    name: 'FeedbackAnalysis',
    description: "Analyzes feedback data and calculates inter-rater reliability using Gwet's AC1 agreement coefficient.",
    href: '/documentation/report-blocks/feedback-analysis',
    badge: 'Analytics',
    features: [
      "AC1 Agreement Coefficient",
      "Accuracy Metrics",
      "Confusion Matrix",
      "Score-by-score Breakdown",
    ]
  },
  {
    name: 'TopicAnalysis',
    description: 'Performs NLP analysis to identify and categorize topics in text data using BERTopic.',
    href: '/documentation/report-blocks/topic-analysis',
    badge: 'NLP',
    features: [
      "BERTopic Clustering",
      "Topic Visualization",
      "Keyword Extraction",
      "Representative Examples",
    ]
  }
];

export default function ReportBlocksPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-4">Report Blocks</h1>
        <p className="text-lg text-muted-foreground leading-relaxed">
          Report blocks are modular components that generate specific types of analysis and visualizations 
          within reports. Each block focuses on a particular analytical task and can be combined to create 
          comprehensive reports.
        </p>
      </div>

      <div className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">What are Report Blocks?</h2>
        <div className="space-y-4 text-muted-foreground">
          <p>
            Report blocks are the building blocks of the Plexus reporting system. Each block:
          </p>
          <ul className="list-disc list-inside space-y-2 ml-4">
            <li>Performs a specific type of analysis on your data</li>
            <li>Generates structured output with visualizations and insights</li>
            <li>Can be configured with parameters to customize the analysis</li>
            <li>Produces both raw data and formatted presentations</li>
            <li>Supports file attachments for detailed exports</li>
          </ul>
          <p>
            Report blocks are implemented as Python classes that inherit from{" "}
            <code className="text-sm bg-muted px-1 py-0.5 rounded">BaseReportBlock</code>{" "}
            and have corresponding React components for visualization in the dashboard.
          </p>
        </div>
      </div>

      <div className="mb-8">
        <h2 className="text-2xl font-semibold mb-6">Available Report Blocks</h2>
        <div className="grid gap-6 md:grid-cols-1 lg:grid-cols-2">
          {blockTypes.map((block) => (
            <Card key={block.name} className="hover:shadow-md transition-shadow border-0">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-xl">
                      <Link
                        href={block.href}
                        className="hover:text-primary transition-colors"
                      >
                        {block.name}
                      </Link>
                    </CardTitle>
                    <Badge className="mt-1">{block.badge}</Badge>
                  </div>
                </div>
                <CardDescription className="text-base leading-relaxed pt-2">
                  {block.description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <h4 className="font-medium text-sm text-foreground">Key Features:</h4>
                  <ul className="grid grid-cols-1 gap-1 text-sm text-muted-foreground">
                    {block.features.map(feature => (
                      <li key={feature} className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 bg-primary rounded-full flex-shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  <div className="pt-2">
                    <Link href={block.href}>
                      <DocButton>View Documentation →</DocButton>
                    </Link>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <div className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Using Report Blocks</h2>
        <div className="space-y-4 text-muted-foreground">
          <p>
            Report blocks are configured in report configuration files using Markdown with embedded code blocks:
          </p>
                      <div className="bg-muted p-4 rounded-lg font-mono text-sm">
              <div className="text-foreground"># My Report</div>
              <div className="text-muted-foreground">This report analyzes feedback data.</div>
              <br />
              <div className="text-foreground">```block</div>
              <div className="text-foreground">class: FeedbackAnalysis</div>
              <div className="text-foreground">scorecard: example_scorecard</div>
              <div className="text-foreground">days: 30</div>
              <div className="text-foreground">```</div>
            </div>
          <p>
            Each block type has its own configuration parameters and generates specific types of output. 
            See the individual block documentation pages for detailed configuration options and examples.
          </p>
        </div>
      </div>

      <div className="bg-muted/50 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-2">Related Documentation</h3>
        <div className="space-y-2">
          <Link href="/documentation/concepts/reports" className="block text-primary hover:text-primary/80">
            Reports Concept Overview →
          </Link>
          <Link href="/documentation/methods/monitor-tasks" className="block text-primary hover:text-primary/80">
            Monitoring Report Generation →
          </Link>
          <Link href="/documentation/advanced/cli" className="block text-primary hover:text-primary/80">
            CLI Report Commands →
          </Link>
        </div>
      </div>
    </div>
  );
}
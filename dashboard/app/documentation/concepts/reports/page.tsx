import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Reports - Plexus Documentation",
  description: "Learn about Reports in Plexus - a flexible system for generating custom analyses and summaries."
}

export default function ReportsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Reports</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Plexus Reports offer a powerful and flexible way to define, generate, and view custom analyses, summaries, and visualizations based on your Plexus data. Instead of building bespoke dashboards for every need, the reporting system provides reusable components and a standardized workflow.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Core Components</h2>
          <p className="text-muted-foreground mb-4">
            The reporting system is built around four key concepts:
          </p>
          <ul className="list-disc pl-6 space-y-4 text-muted-foreground">
            <li>
              <strong className="text-foreground">Report Configuration (`ReportConfiguration`)</strong>
              <p>
                This is the template or blueprint for a specific type of report. It's typically defined using Markdown mixed with simple configuration blocks. It specifies the static content (text, headers), the dynamic analysis blocks to include, and any parameters needed for those blocks. Configurations are stored and managed within Plexus, allowing reuse.
              </p>
              <p className="mt-2">Think of it like a recipe for generating a specific kind of analysis.</p>
              <pre className="bg-muted rounded-lg mt-2">
                <div className="code-container p-4">
                  <code>{`# Score Performance Report

This report analyzes the performance of the 'Agent Professionalism' score.

\`\`\`block name="Professionalism Score Analysis"
class: ScorePerformanceBlock
scorecard: "Customer Service v2"
score: "Agent Professionalism"
time_range: last_30_days
\`\`\`
`}</code>
                </div>
              </pre>
            </li>
            <li>
              <strong className="text-foreground">Report (`Report`)</strong>
              <p>
                This represents a specific instance of a report generated from a `ReportConfiguration` at a particular time, potentially with specific runtime parameters. It stores the final rendered output (e.g., the Markdown content after processing) and links to the results of the individual analysis blocks.
              </p>
              <p className="mt-2">If the Configuration is the recipe, the Report is the finished cake, baked on a specific day.</p>
            </li>
            <li>
              <strong className="text-foreground">Report Block (`ReportBlock`)</strong>
              <p>
                These are the reusable Python components that perform the actual data fetching and analysis for specific sections within a report. Examples might include `ScorePerformanceBlock`, `FeedbackTopicAnalysisBlock`, or `SentimentTrendBlock`. When a report is generated, the system executes the Python code for each block defined in the configuration.
              </p>
              <p className="mt-2">
                Each block generates structured data (usually JSON) containing its findings (e.g., metrics, lists of feedback, chart data) and optionally logs. This structured output is stored alongside the final report.
              </p>
            </li>
            <li>
              <strong className="text-foreground">Task Integration (`Task`)</strong>
              <p>
                Generating a report, especially one involving multiple complex analysis blocks, can take time. Plexus leverages the existing `Task` system to manage report generation as a background job. When you request a new report, a `Task` is created to handle the process. You can monitor the report's progress (Initializing, Running Blocks, Finalizing, Completed/Failed) through the standard Task interface, ensuring consistency with other background operations like Evaluations. The `Report` record itself is directly linked to its corresponding `Task` record.
              </p>
            </li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How It Works</h2>
          <p className="text-muted-foreground mb-6">
            The typical workflow for using reports involves these steps:
          </p>
          <ol className="list-decimal pl-6 space-y-4 text-muted-foreground">
            <li>
              <strong className="text-foreground">Define a `ReportConfiguration`</strong>
              <p>Create a template (using Markdown and block definitions) for the type of report you need. This is often done once and then reused. You might use the CLI or eventually a UI editor.</p>
              <p>Create a template (using Markdown and block definitions) for the type of report you need. This is often done once and then reused. This can be done using the Plexus CLI, the Dashboard UI, or programmatically via the API/SDK (used by AI agents).</p>
              <pre className="bg-muted rounded-lg mt-2">
                <div className="code-container p-4">
                  <code>{`# Example: Creating a config from a file
python -m plexus.cli.CommandLineInterface report config create --name "Agent Prof Report" --file agent_prof_report.md`}</code>
                </div>
              </pre>
            </li>
            <li>
              <strong className="text-foreground">Run the Report</strong>
              <p>Trigger the generation of a new `Report` based on a chosen `ReportConfiguration`. This creates a `Task` to handle the background processing.</p>
               <pre className="bg-muted rounded-lg mt-2">
                <div className="code-container p-4">
                  <code>{`# Example: Running the report
python -m plexus.cli.CommandLineInterface report run --config "Agent Prof Report"`}</code>
                </div>
              </pre>
            </li>
            <li>
              <strong className="text-foreground">Monitor the Task</strong>
              <p>Track the progress of the report generation via the associated `Task`.</p>
            </li>
            <li>
              <strong className="text-foreground">View the `Report`</strong>
              <p>Once the task is complete, view the generated `Report`. This includes the rendered output (e.g., Markdown display) and access to the structured data generated by each `ReportBlock` for deeper dives or visualization.</p>
               <pre className="bg-muted rounded-lg mt-2">
                <div className="code-container p-4">
                  <code>{`# Example: Viewing the latest generated report
python -m plexus.cli.CommandLineInterface report last`}</code>
                </div>
              </pre>
            </li>
          </ol>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Benefits</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong className="text-foreground">Flexibility:</strong> Define custom analyses without needing new API endpoints or dedicated UI pages for each report type.</li>
            <li><strong className="text-foreground">Reusability:</strong> Report Configurations and Report Blocks can be reused across different reports.</li>
            <li><strong className="text-foreground">Consistency:</strong> Leverages the standard `Task` system for progress tracking and status updates.</li>
            <li><strong className="text-foreground">Extensibility:</strong> New analysis types can be added by creating new Python `ReportBlock` classes.</li>
            <li><strong className="text-foreground">Structured Data:</strong> Provides both human-readable output (Markdown) and machine-readable structured data (JSON) from analysis blocks.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Explore how Reports integrate with other core concepts like Scores and Evaluations. Check the CLI documentation for detailed commands on managing and running reports, or browse the available report blocks to see what types of analysis you can include in your reports.
          </p>
          <div className="flex gap-4">
            <Link href="/documentation/concepts">
              <DocButton variant="outline">Back to Core Concepts</DocButton>
            </Link>
            <Link href="/documentation/report-blocks">
              <DocButton>Browse Report Blocks</DocButton>
            </Link>
            {/* Add link to specific CLI docs page when available */}
            {/* <Link href="/documentation/cli/reports">
              <DocButton>View Report CLI Commands</DocButton>
            </Link> */}
          </div>
        </section>
      </div>
    </div>
  )
} 
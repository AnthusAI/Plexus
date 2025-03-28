import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Score Results - Plexus Documentation",
  description: "Learn about Score Results in Plexus - the records of scoring items against scores in a scorecard"
}

export default function ScoreResultsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Score Results</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Score Results record the outcomes of scoring items against scores in a scorecard, providing detailed information about the evaluation process and results.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Score Results?</h2>
          <p className="text-muted-foreground mb-4">
            A Score Result is a record created when an item is evaluated against a score or scores in a scorecard. 
            It captures not only the outcome of the evaluation but also important contextual information about how 
            the evaluation was performed and what data was used.
          </p>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Core Components</h3>
              <p className="text-muted-foreground mb-4">
                Each Score Result contains these essential components:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Value</strong>: The actual result of the evaluation (e.g., "yes"/"no", a numeric score, or a category)
                </li>
                <li>
                  <strong>Confidence</strong>: For applicable scores, indicates how certain the system is about the result
                </li>
                <li>
                  <strong>Correct</strong>: A boolean indicating whether the result matches the expected outcome (for labeled data)
                </li>
                <li>
                  <strong>Explanation</strong>: A detailed description of why this result was chosen, providing transparency into the decision-making process
                </li>
                <li>
                  <strong>Metadata</strong>: Contextual information including the inputs used for evaluation and other relevant data
                </li>
                <li>
                  <strong>Trace</strong>: A detailed record of the evaluation process, including intermediate steps and decisions
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Relationships</h3>
              <p className="text-muted-foreground mb-4">
                Score Results are connected to several other entities in the Plexus system:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Item</strong>: The content being evaluated (e.g., a conversation transcript, document, or other data)
                </li>
                <li>
                  <strong>Score</strong>: The specific evaluation criteria being applied
                </li>
                <li>
                  <strong>Scorecard</strong>: The collection of scores that the individual score belongs to
                </li>
                <li>
                  <strong>Scoring Job</strong>: The process that generated this result (may be part of a larger evaluation)
                </li>
                <li>
                  <strong>Evaluation</strong>: The broader evaluation process that may include multiple scoring jobs and results
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding Score Result Data</h2>
          <p className="text-muted-foreground mb-4">
            Score Results provide rich information that can be used for analysis, debugging, and improving your evaluation processes.
          </p>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Metadata</h3>
              <p className="text-muted-foreground mb-4">
                The metadata field contains contextual information about the evaluation, which may include:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Input Data</strong>: The specific content that was evaluated
                </li>
                <li>
                  <strong>Human Labels</strong>: For labeled data, the expected outcomes provided by human reviewers
                </li>
                <li>
                  <strong>Session Information</strong>: Identifiers for the evaluation session or batch
                </li>
                <li>
                  <strong>Configuration Details</strong>: Specific settings used for this evaluation
                </li>
              </ul>
              <p className="text-muted-foreground mt-4">
                Metadata is valuable for understanding the context of each result and for filtering or grouping results during analysis.
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Trace</h3>
              <p className="text-muted-foreground mb-4">
                The trace field provides a detailed record of the evaluation process, which is especially valuable for complex evaluations like those performed by LLMs or multi-step processes. A trace may include:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Intermediate Steps</strong>: The sequence of operations performed during evaluation
                </li>
                <li>
                  <strong>LLM Prompts and Responses</strong>: For LLM-based evaluations, the exact prompts sent and responses received
                </li>
                <li>
                  <strong>Decision Points</strong>: Key decision points in the evaluation process
                </li>
                <li>
                  <strong>Timing Information</strong>: Performance metrics for different stages of the evaluation
                </li>
              </ul>
              <p className="text-muted-foreground mt-4">
                Traces are invaluable for debugging, understanding model behavior, and improving evaluation processes over time.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Working with Score Results</h2>
          <p className="text-muted-foreground mb-4">
            Plexus provides several ways to work with Score Results, both through the dashboard interface and the CLI.
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Viewing Results in the Dashboard</h3>
              <p className="text-muted-foreground mb-4">
                The Plexus dashboard provides a user-friendly interface for viewing and analyzing Score Results:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Item Detail View</strong>: See all Score Results for a specific item
                </li>
                <li>
                  <strong>Evaluation Results</strong>: View aggregated results from evaluation runs
                </li>
                <li>
                  <strong>Scoring Job Details</strong>: Examine the results of individual scoring jobs
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using the CLI</h3>
              <p className="text-muted-foreground mb-4">
                The Plexus CLI provides powerful commands for working with Score Results:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`# List recent score results for a specific scorecard
plexus results list --scorecard "Example Scorecard" --limit 20

# List recent score results for a specific account
plexus results list --account "Example Account" --limit 20

# Get detailed information about a specific score result
plexus results info --id "result-id-here"`}</code>
                </div>
              </pre>
              <p className="text-muted-foreground">
                These commands provide detailed views of Score Results, including pretty-printed metadata and trace information for in-depth analysis.
              </p>
            </div>
          </div>
          
          <div className="flex gap-4 mt-6">
            <Link href="/documentation/concepts/scores">
              <DocButton>Learn about Scores</DocButton>
            </Link>
            <Link href="/documentation/advanced/cli">
              <DocButton variant="outline">CLI Reference</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 
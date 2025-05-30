import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Basics - Plexus Documentation",
  description: "Learn about the core concepts in Plexus"
}

export default function BasicsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Core Concepts</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn about the fundamental building blocks that make up Plexus.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Core Concepts</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-xl font-medium mb-2">Items</h3>
              <p className="text-muted-foreground mb-4">
                Individual pieces of content that you want to analyze or evaluate using Plexus. Items are the core units that get scored.
              </p>
              <Link href="/documentation/basics/items">
                <DocButton>Learn about Items</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Sources</h3>
              <p className="text-muted-foreground mb-4">
                Input data for evaluation, including text and audio content. Sources are the foundation
                of content analysis in Plexus.
              </p>
              <Link href="/documentation/basics/sources">
                <DocButton>Learn about Sources</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Scores</h3>
              <p className="text-muted-foreground mb-4">
                Individual evaluation criteria that define what to measure. Scores are the building blocks
                of scorecards and can range from simple questions to complex metrics.
              </p>
              <Link href="/documentation/basics/scores">
                <DocButton>Learn about Scores</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Scorecards</h3>
              <p className="text-muted-foreground mb-4">
                Collections of scores that form a complete evaluation framework. Scorecards organize
                related evaluation criteria into meaningful groups.
              </p>
              <Link href="/documentation/basics/scorecards">
                <DocButton>Learn about Scorecards</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Evaluations</h3>
              <p className="text-muted-foreground mb-4">
                The process of analyzing sources using scorecards to generate insights
                and quality metrics.
              </p>
              <Link href="/documentation/basics/evaluations">
                <DocButton>Understand Evaluations</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Tasks</h3>
              <p className="text-muted-foreground mb-4">
                Individual units of work in Plexus, representing operations like source processing
                and evaluations.
              </p>
              <Link href="/documentation/basics/tasks">
                <DocButton>Discover Tasks</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Reports</h3>
              <p className="text-muted-foreground mb-4">
                Flexible, template-driven analyses and summaries generated from your Plexus data using reusable components.
              </p>
              <Link href="/documentation/concepts/reports">
                <DocButton>Learn about Reports</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Evaluation Metrics</h3>
              <p className="text-muted-foreground mb-4">
                Specialized visualization tools that help interpret agreement and accuracy metrics, especially when dealing with imbalanced data.
              </p>
              <Link href="/documentation/concepts/evaluation-metrics">
                <DocButton>Understand Evaluation Metrics</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How It All Works Together</h2>
          <p className="text-muted-foreground mb-6">
            The Plexus workflow follows a simple pattern:
          </p>
          <ol className="list-decimal pl-6 space-y-4 text-muted-foreground">
            <li>
              <strong className="text-foreground">Create Sources</strong>
              <p>Upload or connect your content for analysis.</p>
            </li>
            <li>
              <strong className="text-foreground">Define Scorecards</strong>
              <p>Set up evaluation criteria and scoring rules.</p>
            </li>
            <li>
              <strong className="text-foreground">Run Evaluations</strong>
              <p>Process sources using your scorecards.</p>
            </li>
            <li>
              <strong className="text-foreground">Monitor Tasks & View Reports</strong>
              <p>Track progress of evaluations and report generation, then review the results and generated reports.</p>
            </li>
          </ol>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Start with Sources to learn how to add content to Plexus, then explore Scorecards
            to understand how to evaluate your content effectively.
          </p>
          <div className="flex gap-4">
            <Link href="/documentation/basics/sources">
              <DocButton>Get Started with Sources</DocButton>
            </Link>
            <Link href="/documentation/methods">
              <DocButton variant="outline">View Step-by-Step Guides</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 
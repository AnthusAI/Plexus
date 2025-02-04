import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Methods - Plexus Documentation",
  description: "Step-by-step guides for common operations and workflows in Plexus."
}

export default function MethodsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Methods</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Step-by-step guides for common operations and workflows in Plexus.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Source Management</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Adding and Editing Sources</h3>
              <p className="text-muted-foreground mb-4">
                Learn how to create new sources and manage existing ones through the dashboard.
              </p>
              <Link href="/documentation/methods/add-edit-source">
                <DocButton>View Source Management Guide</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Source Profiling</h3>
              <p className="text-muted-foreground mb-4">
                Understand how to analyze your sources to gain insights into their characteristics.
              </p>
              <Link href="/documentation/methods/profile-source">
                <DocButton>Learn About Profiling</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Evaluation Setup</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Creating Scorecards</h3>
              <p className="text-muted-foreground mb-4">
                Set up comprehensive evaluation criteria with custom scorecards.
              </p>
              <Link href="/documentation/methods/add-edit-scorecard">
                <DocButton>Explore Scorecard Creation</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Configuring Scores</h3>
              <p className="text-muted-foreground mb-4">
                Define individual evaluation metrics and their parameters.
              </p>
              <Link href="/documentation/methods/add-edit-score">
                <DocButton>Configure Score Settings</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Running Evaluations</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Evaluating Content</h3>
              <p className="text-muted-foreground mb-4">
                Process your sources using scorecards to generate insights.
              </p>
              <Link href="/documentation/methods/evaluate-score">
                <DocButton>Start Evaluating Content</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Task Management</h3>
              <p className="text-muted-foreground mb-4">
                Track and manage evaluation tasks through their lifecycle.
              </p>
              <Link href="/documentation/methods/monitor-tasks">
                <DocButton>Monitor Your Tasks</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Ready to get started? Begin with source management to set up your content for evaluation.
          </p>
          <div className="flex gap-4">
            <Link href="/documentation/methods/add-edit-source">
              <DocButton>Start Managing Sources</DocButton>
            </Link>
            <Link href="/documentation/basics">
              <DocButton variant="outline">Review Core Concepts</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 
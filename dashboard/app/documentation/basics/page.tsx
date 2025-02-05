import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Basics - Plexus Documentation",
  description: "Learn about the core concepts and components that make up the Plexus platform."
}

export default function BasicsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Basics</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn about the core concepts and components that make up the Plexus platform.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Core Concepts</h2>
          <div className="grid gap-6 sm:grid-cols-2">
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
              <h3 className="text-xl font-medium mb-2">Scorecards</h3>
              <p className="text-muted-foreground mb-4">
                Collections of evaluation criteria that define how content should be analyzed
                and scored.
              </p>
              <Link href="/documentation/basics/scorecards">
                <DocButton>Explore Scorecards</DocButton>
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
              <strong className="text-foreground">Monitor Tasks</strong>
              <p>Track progress and review results.</p>
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
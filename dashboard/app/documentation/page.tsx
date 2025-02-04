import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"

export default function DocumentationPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Documentation</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Welcome to the Plexus documentation. Here you'll find comprehensive guides and documentation
        to help you start working with Plexus as quickly as possible.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Getting Started</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-xl font-medium mb-2">Core Concepts</h3>
              <p className="text-muted-foreground mb-4">
                Learn about the fundamental concepts and components that power Plexus.
              </p>
              <Link href="/documentation/basics">
                <DocButton>Explore Basics</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Step-by-Step Guides</h3>
              <p className="text-muted-foreground mb-4">
                Follow detailed guides for common operations and workflows.
              </p>
              <Link href="/documentation/methods">
                <DocButton>View Methods</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Platform Components</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-xl font-medium mb-2">Worker Nodes</h3>
              <p className="text-muted-foreground mb-4">
                Set up and manage worker nodes to process your content at scale.
              </p>
              <Link href="/documentation/worker-nodes">
                <DocButton>Learn About Workers</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">
                <code className="text-lg">plexus</code> CLI Tool
              </h3>
              <p className="text-muted-foreground mb-4">
                Use the command-line interface to manage your Plexus deployment.
              </p>
              <Link href="/documentation/cli">
                <DocButton>Explore CLI</DocButton>
              </Link>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Python SDK</h3>
              <p className="text-muted-foreground mb-4">
                Integrate Plexus into your Python applications programmatically.
              </p>
              <Link href="/documentation/sdk">
                <DocButton>Browse SDK Reference</DocButton>
              </Link>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Quick Start</h2>
          <p className="text-muted-foreground mb-6">
            The fastest way to get started with Plexus is to:
          </p>
          <ol className="list-decimal pl-6 space-y-4 text-muted-foreground">
            <li>
              <strong className="text-foreground">Review the Basics</strong>
              <p>Understand the core concepts that make up Plexus.</p>
            </li>
            <li>
              <strong className="text-foreground">Create Your First Source</strong>
              <p>Add some content to analyze using the dashboard.</p>
            </li>
            <li>
              <strong className="text-foreground">Set Up a Scorecard</strong>
              <p>Define how you want to evaluate your content.</p>
            </li>
            <li>
              <strong className="text-foreground">Run an Evaluation</strong>
              <p>Process your content and view the results.</p>
            </li>
          </ol>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Ready to get started? Begin with the basics to understand Plexus's core concepts.
          </p>
          <div className="flex gap-4">
            <Link href="/documentation/basics">
              <DocButton>Start with Basics</DocButton>
            </Link>
            <Link href="/documentation/methods/add-edit-source">
              <DocButton variant="outline">Jump to Source Creation</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 
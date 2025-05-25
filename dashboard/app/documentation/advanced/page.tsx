import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Advanced - Plexus Documentation",
  description: "Advanced tools and concepts for power users of the Plexus platform."
}

export default function AdvancedPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Advanced Tools & Concepts</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Explore advanced tools and concepts that enable deeper integration and customization of Plexus 
        for technical users and developers.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Command Line Interface</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              The <code>plexus</code> CLI tool provides powerful command-line access to all Plexus functionality, 
              perfect for automation and advanced workflows.
            </p>
            <Link href="/documentation/advanced/cli">
              <DocButton>Explore CLI Tool</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Worker Infrastructure</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              Learn how to set up and manage Plexus worker nodes to process tasks efficiently 
              across your infrastructure.
            </p>
            <Link href="/documentation/advanced/worker-nodes">
              <DocButton>Learn About Workers</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              Integrate Plexus directly into your Python applications with our comprehensive SDK, 
              enabling programmatic access to all platform features.
            </p>
            <Link href="/documentation/advanced/sdk">
              <DocButton>Browse SDK Reference</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Universal Code Snippets</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              Learn about Plexus's universal YAML code format designed for seamless communication 
              between humans, AI models, and other systems.
            </p>
            <Link href="/documentation/advanced/yaml-code-standard">
              <DocButton>Explore Universal Code Snippets</DocButton>
            </Link>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Plexus MCP Server</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              Enable AI agents and tools to interact with Plexus functionality using the Multi-Agent Cooperative Protocol (MCP).
            </p>
            <Link href="/documentation/advanced/mcp-server">
              <DocButton>Explore MCP Server</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
} 
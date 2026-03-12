import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Procedures - Plexus Documentation",
  description: "Learn about Plexus Procedures - a Lua-based DSL for programming agentic workflows with first-class human-in-the-loop support"
}

export default function ProceduresPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Plexus Procedures</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Configuration-based agentic workflow programming with first-class human-in-the-loop support.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Procedures?</h2>
          <p className="text-muted-foreground mb-4">
            Plexus Procedures is a domain-specific language (DSL) that enables you to define sophisticated
            agentic workflows through configuration, combining:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>Declarative YAML</strong> for component definitions (agents, prompts, tools, stages)</li>
            <li><strong>Embedded Lua</strong> for orchestration logic and control flow</li>
            <li><strong>High-level primitives</strong> that abstract LLM mechanics (e.g., <code>Worker.turn()</code>)</li>
            <li><strong>First-class HITL</strong> (Human-in-the-Loop) support for collaboration</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Features</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Uniform Recursion</h3>
              <p className="text-sm text-muted-foreground">
                Procedures work identically at all nesting levels - same parameters, outputs, HITL,
                and async capabilities everywhere.
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Human-in-the-Loop</h3>
              <p className="text-sm text-muted-foreground">
                First-class primitives for approval, input, review, notifications, and alerts built
                directly into workflow control flow.
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Async Operations</h3>
              <p className="text-sm text-muted-foreground">
                Spawn procedures in parallel with simple primitives. Monitor progress and wait for
                results with built-in concurrency support.
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Built-In Reliability</h3>
              <p className="text-sm text-muted-foreground">
                Automatic retries, validation, error handling, and recovery patterns under the hood.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Quick Example</h2>
          <p className="text-muted-foreground mb-4">
            Here's a simple procedure that researches a topic and requests human approval:
          </p>
          <pre className="bg-muted rounded-lg overflow-x-auto">
            <div className="code-container p-4">
              <code>{`name: content_reviewer
version: 1.0.0

params:
  topic:
    type: string
    required: true

outputs:
  approved:
    type: boolean
    required: true

agents:
  researcher:
    system_prompt: |
      Research and summarize: {params.topic}
    tools: [search, done]

workflow: |
  -- AI does research
  repeat
    Researcher.turn()
  until Tool.called("done")

  -- Human approves
  local approved = Human.approve({
    message = "Approve this research?",
    context = {findings = State.get("findings")}
  })

  return {approved = approved}`}</code>
            </div>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Core Concepts</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Procedures</h3>
              <p className="text-muted-foreground">
                Reusable units of agentic work that accept typed parameters, return typed outputs,
                and can invoke other procedures recursively.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Agents</h3>
              <p className="text-muted-foreground">
                Configured LLM instances with system prompts, tools, and behavior settings. Each agent
                becomes a Lua primitive (e.g., <code>Worker.turn()</code>).
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Workflows</h3>
              <p className="text-muted-foreground">
                Lua orchestration code that controls execution flow, manages state, invokes agents,
                and handles human interaction.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">State & Stages</h3>
              <p className="text-muted-foreground">
                Mutable storage for tracking progress across turns, and high-level workflow phases
                for monitoring and status reporting.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Message Classification</h2>
          <p className="text-muted-foreground mb-4">
            Every message in Plexus has a <code>humanInteraction</code> classification that determines
            visibility and behavior:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>INTERNAL</strong> - Agent reasoning hidden from humans</li>
            <li><strong>CHAT / CHAT_ASSISTANT</strong> - Conversational AI messages</li>
            <li><strong>NOTIFICATION</strong> - Workflow progress updates</li>
            <li><strong>ALERT_*</strong> - System monitoring alerts</li>
            <li><strong>PENDING_*</strong> - Requests requiring human response</li>
          </ul>
          <p className="text-muted-foreground mt-4">
            This unified system enables different UIs to filter messages appropriately - operator dashboards
            see notifications and requests, monitoring sees alerts, debugging sees everything.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Documentation</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link href="/documentation/procedures/getting-started">
              <div className="border rounded-lg p-4 hover:bg-muted transition-colors cursor-pointer">
                <h3 className="text-lg font-medium mb-2">Getting Started</h3>
                <p className="text-sm text-muted-foreground">
                  Learn the basics and write your first procedure
                </p>
              </div>
            </Link>
            <Link href="/documentation/procedures/hitl">
              <div className="border rounded-lg p-4 hover:bg-muted transition-colors cursor-pointer">
                <h3 className="text-lg font-medium mb-2">Human-in-the-Loop</h3>
                <p className="text-sm text-muted-foreground">
                  Master collaboration patterns with humans
                </p>
              </div>
            </Link>
            <Link href="/documentation/procedures/examples">
              <div className="border rounded-lg p-4 hover:bg-muted transition-colors cursor-pointer">
                <h3 className="text-lg font-medium mb-2">Examples & Patterns</h3>
                <p className="text-sm text-muted-foreground">
                  Real-world examples from simple to complex
                </p>
              </div>
            </Link>
            <Link href="/documentation/procedures/api">
              <div className="border rounded-lg p-4 hover:bg-muted transition-colors cursor-pointer">
                <h3 className="text-lg font-medium mb-2">API Reference</h3>
                <p className="text-sm text-muted-foreground">
                  Complete reference for all Lua primitives
                </p>
              </div>
            </Link>
            <Link href="/documentation/procedures/messages">
              <div className="border rounded-lg p-4 hover:bg-muted transition-colors cursor-pointer">
                <h3 className="text-lg font-medium mb-2">Message Classification</h3>
                <p className="text-sm text-muted-foreground">
                  Understand message types and visibility
                </p>
              </div>
            </Link>
            <Link href="/documentation/procedures/spec">
              <div className="border rounded-lg p-4 hover:bg-muted transition-colors cursor-pointer">
                <h3 className="text-lg font-medium mb-2">Technical Specification</h3>
                <p className="text-sm text-muted-foreground">
                  Complete DSL specification and reference
                </p>
              </div>
            </Link>
          </div>
        </section>

        <section className="bg-muted rounded-lg p-6">
          <h2 className="text-2xl font-semibold mb-4">Additional Resources</h2>
          <div className="space-y-2">
            <p className="text-muted-foreground">
              <strong>AGENTS.md:</strong> Comprehensive technical specification located at{" "}
              <code className="text-sm bg-background px-2 py-1 rounded">/plexus/procedures/AGENTS.md</code>
            </p>
            <p className="text-muted-foreground">
              <strong>HTML Documentation:</strong> Complete standalone HTML documentation available at{" "}
              <code className="text-sm bg-background px-2 py-1 rounded">/plexus/procedures/docs/</code>
            </p>
            <p className="text-muted-foreground">
              <strong>GitHub:</strong>{" "}
              <a href="https://github.com/AnthusAI/Plexus" className="text-primary hover:underline">
                github.com/AnthusAI/Plexus
              </a>
            </p>
          </div>
        </section>

        <div className="flex gap-4 mt-8">
          <Link href="/documentation/procedures/getting-started">
            <DocButton>Get Started</DocButton>
          </Link>
          <Link href="/documentation/procedures/spec">
            <DocButton variant="outline">View Full Specification</DocButton>
          </Link>
        </div>
      </div>
    </div>
  )
}

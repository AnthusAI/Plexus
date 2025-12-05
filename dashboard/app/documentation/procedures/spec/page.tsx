import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"
import { FileText, Download } from "lucide-react"

export const metadata: Metadata = {
  title: "Technical Specification - Procedures - Plexus Documentation",
  description: "Complete technical specification for the Plexus Procedure DSL"
}

export default function ProceduresSpecPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Procedure DSL Technical Specification</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Complete reference for the Plexus Procedure DSL v4.0.0
      </p>

      <div className="space-y-8">
        <section className="bg-muted rounded-lg p-6">
          <div className="flex items-start gap-4">
            <FileText className="h-8 w-8 text-primary mt-1" />
            <div className="flex-1">
              <h2 className="text-2xl font-semibold mb-2">AGENTS.md</h2>
              <p className="text-muted-foreground mb-4">
                The complete technical specification is available in <code>AGENTS.md</code> at{" "}
                <code className="text-sm bg-background px-2 py-1 rounded">/plexus/procedures/AGENTS.md</code>
              </p>
              <p className="text-muted-foreground mb-4">
                This comprehensive 45KB document covers every aspect of the Procedure DSL including:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-muted-foreground mb-4">
                <li>Complete document structure and YAML schema</li>
                <li>All primitives and API reference</li>
                <li>Human-in-the-Loop patterns</li>
                <li>Message classification system</li>
                <li>Real-world examples</li>
                <li>Best practices and migration guides</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">HTML Documentation</h2>
          <p className="text-muted-foreground mb-4">
            Comprehensive HTML documentation is also available at{" "}
            <code className="text-sm bg-muted px-2 py-1 rounded">/plexus/procedures/docs/</code>
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-medium mb-2">index.html</h3>
              <p className="text-sm text-muted-foreground">Landing page with overview and navigation</p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-medium mb-2">getting-started.html</h3>
              <p className="text-sm text-muted-foreground">Step-by-step tutorial and examples</p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-medium mb-2">hitl-guide.html</h3>
              <p className="text-sm text-muted-foreground">Human-in-the-Loop patterns and primitives</p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-medium mb-2">examples.html</h3>
              <p className="text-sm text-muted-foreground">8 complete real-world examples</p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-medium mb-2">api-reference.html</h3>
              <p className="text-sm text-muted-foreground">Complete API with all primitives</p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-medium mb-2">message-classification.html</h3>
              <p className="text-sm text-muted-foreground">Message types and visibility system</p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Sections</h2>
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-2">Document Structure</h3>
              <p className="text-muted-foreground mb-2">
                Every procedure is defined in YAML with these sections:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-sm text-muted-foreground">
                <li>Metadata: name, version, description</li>
                <li>Parameters: typed input schema</li>
                <li>Outputs: typed return schema</li>
                <li>Guards: pre-execution validation</li>
                <li>HITL: human interaction points</li>
                <li>Agents: LLM worker configurations</li>
                <li>Stages: workflow phase tracking</li>
                <li>Workflow: Lua orchestration code</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Primitive Categories</h3>
              <p className="text-muted-foreground mb-2">
                The DSL provides high-level primitives in these categories:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-sm text-muted-foreground">
                <li><strong>Procedure:</strong> run, spawn, wait, status, inject, cancel</li>
                <li><strong>Agent:</strong> turn (e.g., Worker.turn())</li>
                <li><strong>Human:</strong> approve, input, review, notify, escalate</li>
                <li><strong>System:</strong> alert</li>
                <li><strong>State:</strong> get, set, increment, append, all</li>
                <li><strong>Stage:</strong> set, current, is, advance, history</li>
                <li><strong>Tool:</strong> called, last_result, last_call</li>
                <li><strong>Session:</strong> append, inject_system, clear, history</li>
                <li><strong>Control:</strong> Stop, Iterations</li>
                <li><strong>Utility:</strong> Log, Sleep, Json, File, Retry</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Design Philosophy</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li><strong>YAML declares, Lua orchestrates</strong> - Separation of configuration and control flow</li>
                <li><strong>High-level primitives</strong> - Simple operations hide complex LLM mechanics</li>
                <li><strong>Uniform recursion</strong> - Procedures work identically at all nesting levels</li>
                <li><strong>Human-in-the-loop first</strong> - Collaboration patterns built into the core</li>
                <li><strong>Built-in reliability</strong> - Retries, validation, and recovery under the hood</li>
              </ul>
            </div>
          </div>
        </section>

        <section className="bg-muted rounded-lg p-6">
          <h2 className="text-2xl font-semibold mb-4">Quick Reference</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-medium mb-2">Minimal Procedure</h3>
              <pre className="bg-background rounded p-3 text-sm overflow-x-auto">
                <code>{`name: simple_task
version: 1.0.0

agents:
  worker:
    system_prompt: "Complete the task"
    tools: [done]

workflow: |
  Worker.turn()`}</code>
              </pre>
            </div>

            <div>
              <h3 className="text-lg font-medium mb-2">With HITL</h3>
              <pre className="bg-background rounded p-3 text-sm overflow-x-auto">
                <code>{`workflow: |
  Worker.turn()

  local approved = Human.approve({
    message = "Proceed?",
    timeout = 3600
  })

  if approved then
    execute()
  end`}</code>
              </pre>
            </div>

            <div>
              <h3 className="text-lg font-medium mb-2">Async Invocation</h3>
              <pre className="bg-background rounded p-3 text-sm overflow-x-auto">
                <code>{`workflow: |
  -- Spawn in parallel
  local handles = {}
  for _, topic in ipairs(params.topics) do
    local h = Procedure.spawn("researcher", {topic = topic})
    table.insert(handles, h)
  end

  -- Wait for all
  Procedure.wait_all(handles)

  -- Collect results
  local results = {}
  for _, h in ipairs(handles) do
    table.insert(results, Procedure.result(h))
  end`}</code>
              </pre>
            </div>
          </div>
        </section>

        <div className="flex gap-4 mt-8">
          <Link href="/documentation/procedures/getting-started">
            <DocButton>Getting Started</DocButton>
          </Link>
          <Link href="/documentation/procedures/api">
            <DocButton variant="outline">API Reference</DocButton>
          </Link>
        </div>
      </div>
    </div>
  )
}

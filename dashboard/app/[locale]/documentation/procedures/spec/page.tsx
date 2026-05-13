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
              <h2 className="text-2xl font-semibold mb-2">Documentation Files</h2>
              <p className="text-muted-foreground mb-4">
                The Procedure DSL documentation is maintained in the codebase at{" "}
                <code className="text-sm bg-background px-2 py-1 rounded">/plexus/procedures/</code>
              </p>

              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-medium mb-1">DSL_SPECIFICATION.md</h3>
                  <p className="text-sm text-muted-foreground mb-2">
                    Complete technical specification (~65KB) covering every aspect of the DSL:
                  </p>
                  <ul className="list-disc pl-6 space-y-1 text-sm text-muted-foreground">
                    <li>Complete document structure and YAML schema</li>
                    <li>All primitives and API reference</li>
                    <li>Human-in-the-Loop patterns and execution contexts</li>
                    <li>Message classification system</li>
                    <li>Idempotent execution model</li>
                    <li>Real-world examples with full code</li>
                  </ul>
                </div>

                <div>
                  <h3 className="text-lg font-medium mb-1">AGENTS.md</h3>
                  <p className="text-sm text-muted-foreground">
                    Quick reference guide (~3KB) with common patterns and a pointer to the full spec.
                    Optimized for AI coding agents to load efficiently.
                  </p>
                </div>

                <div>
                  <h3 className="text-lg font-medium mb-1">Working Examples</h3>
                  <p className="text-sm text-muted-foreground mb-2">
                    Live, tested procedure examples:
                  </p>
                  <ul className="list-disc pl-6 space-y-1 text-sm text-muted-foreground">
                    <li><code>limerick_writer.yaml</code> - Basic single-agent loop</li>
                    <li><code>creative_writer.yaml</code> - Multi-agent sequential pipeline</li>
                    <li><code>README.md</code> - Example documentation and usage</li>
                  </ul>
                </div>
              </div>
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

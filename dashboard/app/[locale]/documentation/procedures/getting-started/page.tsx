import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Getting Started - Procedures - Plexus Documentation",
  description: "Learn the basics of Plexus Procedures and write your first agentic workflow"
}

export default function ProceduresGettingStartedPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Getting Started with Procedures</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn the basics and write your first agentic workflow.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Core Concepts</h2>

          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-2">Procedures</h3>
              <p className="text-muted-foreground mb-2">
                A <strong>procedure</strong> is a reusable unit of agentic work defined in YAML. It has:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                <li><strong>Parameters:</strong> Typed inputs validated before execution</li>
                <li><strong>Outputs:</strong> Typed results validated after execution</li>
                <li><strong>Agents:</strong> LLM workers that execute tasks</li>
                <li><strong>Workflow:</strong> Lua orchestration code</li>
                <li><strong>State:</strong> Mutable storage for tracking progress</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Agents</h3>
              <p className="text-muted-foreground mb-2">
                <strong>Agents</strong> are configured LLM instances. Each agent has:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
                <li>A system prompt (can use templates)</li>
                <li>Available tools (including other procedures)</li>
                <li>Response filtering and retry configuration</li>
              </ul>
              <p className="text-muted-foreground mt-2">
                When you define an agent named <code>worker</code>, you get a Lua primitive{" "}
                <code>Worker.turn()</code> that executes one agentic turn.
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Workflows</h3>
              <p className="text-muted-foreground">
                The <strong>workflow</strong> contains Lua code that orchestrates execution: calling agent turns,
                managing state, controlling flow, invoking other procedures, and returning results.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Your First Procedure</h2>

          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-2">Step 1: Simple Research Task</h3>
              <p className="text-muted-foreground mb-4">
                Let's create a procedure that researches a topic:
              </p>
              <pre className="bg-muted rounded-lg overflow-x-auto">
                <div className="code-container p-4">
                  <code>{`name: simple_researcher
version: 1.0.0
description: Research a topic and provide summary

params:
  topic:
    type: string
    required: true

outputs:
  summary:
    type: string
    required: true

agents:
  researcher:
    system_prompt: |
      Research the topic: {params.topic}
      Use the search tool to find information.
      When done, call the done tool.
    tools:
      - search
      - done

workflow: |
  -- Loop until done
  repeat
    Researcher.turn()
  until Tool.called("done") or Iterations.exceeded(10)

  return {summary = State.get("summary") or "No summary available"}`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Step 2: Add State Tracking</h3>
              <p className="text-muted-foreground mb-4">
                Track progress across turns:
              </p>
              <pre className="bg-muted rounded-lg overflow-x-auto">
                <div className="code-container p-4">
                  <code>{`workflow: |
  -- Initialize state
  State.set("count", 0)

  -- Process each item
  for i, item in ipairs(params.items) do
    Worker.turn({inject = "Process: " .. item})
    State.increment("count")
  end

  return {processed_count = State.get("count")}`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Step 3: Add Stages</h3>
              <p className="text-muted-foreground mb-4">
                Use stages for status tracking:
              </p>
              <pre className="bg-muted rounded-lg overflow-x-auto">
                <div className="code-container p-4">
                  <code>{`stages:
  - loading
  - analyzing
  - reporting

workflow: |
  Stage.set("loading")
  load_data()

  Stage.set("analyzing")
  repeat
    Worker.turn()
  until Tool.called("done")

  Stage.set("reporting")
  generate_report()`}</code>
                </div>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Working with Parameters</h2>

          <div className="space-y-4">
            <pre className="bg-muted rounded-lg overflow-x-auto">
              <div className="code-container p-4">
                <code>{`params:
  topic:
    type: string
    required: true
    description: "The research topic"

  depth:
    type: string
    enum: [shallow, deep]
    default: shallow

  max_results:
    type: number
    default: 10

  include_sources:
    type: boolean
    default: true`}</code>
              </div>
            </pre>

            <p className="text-muted-foreground mt-4">
              <strong>Supported types:</strong> <code>string</code>, <code>number</code>,{" "}
              <code>boolean</code>, <code>array</code>, <code>object</code>
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Error Handling</h2>

          <div className="space-y-4">
            <p className="text-muted-foreground">
              Use Lua's <code>pcall</code> for error handling:
            </p>
            <pre className="bg-muted rounded-lg overflow-x-auto">
              <div className="code-container p-4">
                <code>{`workflow: |
  local ok, result = pcall(function()
    Worker.turn()
    return State.get("result")
  end)

  if not ok then
    Log.error("Operation failed: " .. tostring(result))
    return {success = false, error = result}
  end

  return {success = true, result = result}`}</code>
              </div>
            </pre>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Invoking Other Procedures</h2>

          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-2">Synchronous</h3>
              <pre className="bg-muted rounded-lg overflow-x-auto">
                <div className="code-container p-4">
                  <code>{`workflow: |
  -- Call and wait for result
  local research = Procedure.run("researcher", {
    topic = params.topic
  })

  Log.info("Research complete: " .. research.summary)`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Asynchronous</h3>
              <pre className="bg-muted rounded-lg overflow-x-auto">
                <div className="code-container p-4">
                  <code>{`workflow: |
  -- Spawn in background
  local handle = Procedure.spawn("researcher", {
    topic = params.topic
  })

  -- Do other work
  do_something_else()

  -- Wait for result
  local research = Procedure.wait(handle)`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Parallel Execution</h3>
              <pre className="bg-muted rounded-lg overflow-x-auto">
                <div className="code-container p-4">
                  <code>{`workflow: |
  -- Spawn multiple procedures
  local handles = {}
  for _, topic in ipairs(params.topics) do
    local handle = Procedure.spawn("researcher", {topic = topic})
    table.insert(handles, handle)
  end

  -- Wait for all
  Procedure.wait_all(handles)

  -- Collect results
  local results = {}
  for _, handle in ipairs(handles) do
    table.insert(results, Procedure.result(handle))
  end`}</code>
                </div>
              </pre>
            </div>
          </div>
        </section>

        <section className="bg-muted rounded-lg p-6">
          <h2 className="text-2xl font-semibold mb-4">Complete Example</h2>
          <pre className="bg-background rounded-lg overflow-x-auto">
            <div className="code-container p-4">
              <code>{`name: data_processor
version: 1.0.0

params:
  items:
    type: array
    required: true

outputs:
  processed:
    type: number
    required: true

stages:
  - processing
  - complete

agents:
  processor:
    system_prompt: |
      Process items one at a time.
      Progress: {state.processed}/{state.total}
    tools:
      - process_item
      - done

workflow: |
  Stage.set("processing")

  -- Initialize
  State.set("processed", 0)
  State.set("total", #params.items)

  -- Process each item
  for i, item in ipairs(params.items) do
    Processor.turn({inject = "Process: " .. item})
    State.increment("processed")
  end

  Stage.set("complete")
  return {processed = State.get("processed")}`}</code>
            </div>
          </pre>
        </section>

        <div className="flex gap-4 mt-8">
          <Link href="/documentation/procedures/hitl">
            <DocButton>Next: Human-in-the-Loop →</DocButton>
          </Link>
          <Link href="/documentation/procedures/api">
            <DocButton variant="outline">API Reference</DocButton>
          </Link>
        </div>
      </div>
    </div>
  )
}

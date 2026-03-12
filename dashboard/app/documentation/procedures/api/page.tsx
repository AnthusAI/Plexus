import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "API Reference - Procedures - Plexus Documentation",
  description: "Complete API reference for all Plexus Procedure primitives"
}

export default function ProceduresAPIPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Procedure API Reference</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Complete reference for all Lua primitives available in workflows.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4 border-b-2 border-primary pb-2">
            Procedure Primitives
          </h2>
          <p className="text-muted-foreground mb-4">
            Control and monitor other procedures.
          </p>

          <div className="space-y-4">
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Procedure.run(name, params)</h3>
              <p className="text-sm text-muted-foreground mb-2">
                Invoke a procedure synchronously and wait for result.
              </p>
              <p className="text-sm mb-2"><strong>Returns:</strong> Table containing procedure outputs</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`local result = Procedure.run("researcher", {
  topic = "quantum computing"
})
Log.info("Findings: " .. result.findings)`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Procedure.spawn(name, params)</h3>
              <p className="text-sm text-muted-foreground mb-2">
                Spawn a procedure asynchronously and return handle.
              </p>
              <p className="text-sm mb-2"><strong>Returns:</strong> Handle for monitoring</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`local handle = Procedure.spawn("researcher", {
  topic = "quantum computing"
})
-- Do other work
local result = Procedure.wait(handle)`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Procedure.status(handle)</h3>
              <p className="text-sm text-muted-foreground mb-2">
                Get current status of an async procedure.
              </p>
              <p className="text-sm mb-2">
                <strong>Returns:</strong> Table with stage, waiting_for_human, iterations, message
              </p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`local status = Procedure.status(handle)
if status.waiting_for_human then
  notify_slack("Waiting for approval")
end`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Procedure.wait(handle, options)</h3>
              <p className="text-sm text-muted-foreground mb-2">
                Wait for async procedure to complete.
              </p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`local result = Procedure.wait(handle, {timeout = 300})`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4 border-b-2 border-primary pb-2">
            Agent Primitives
          </h2>
          <p className="text-muted-foreground mb-4">
            Execute agent turns. Agent name determines primitive name (e.g., <code>worker</code> → <code>Worker.turn()</code>).
          </p>

          <div className="border rounded-lg p-4">
            <h3 className="text-lg font-mono font-medium mb-2">Agent.turn(options)</h3>
            <p className="text-sm text-muted-foreground mb-2">
              Execute one agent turn.
            </p>
            <p className="text-sm mb-2">
              <strong>Returns:</strong> Table with content and tool_calls
            </p>
            <pre className="bg-muted rounded p-3 text-sm">
              <code>{`-- Basic turn
Worker.turn()

-- With injection
Worker.turn({inject = "Focus on security"})

-- Capture response
local response = Worker.turn()
Log.info(response.content)`}</code>
            </pre>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4 border-b-2 border-primary pb-2">
            Human Primitives
          </h2>
          <p className="text-muted-foreground mb-4">
            Human-in-the-loop interaction.
          </p>

          <div className="space-y-4">
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Human.approve(options)</h3>
              <p className="text-sm text-muted-foreground mb-2">
                Request yes/no approval (blocking).
              </p>
              <p className="text-sm mb-2"><strong>Returns:</strong> Boolean</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`local approved = Human.approve({
  message = "Deploy?",
  context = {version = "2.1.0"},
  timeout = 3600,
  default = false
})`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Human.input(options)</h3>
              <p className="text-sm text-muted-foreground mb-2">
                Request text input (blocking).
              </p>
              <p className="text-sm mb-2"><strong>Returns:</strong> String or nil</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`local topic = Human.input({
  message = "What topic?",
  placeholder = "Enter topic..."
})`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Human.notify(options)</h3>
              <p className="text-sm text-muted-foreground mb-2">
                Send notification (non-blocking).
              </p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`Human.notify({
  message = "Processing phase 2",
  level = "info",
  context = {progress = "40%"}
})`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4 border-b-2 border-primary pb-2">
            State Primitives
          </h2>
          <p className="text-muted-foreground mb-4">
            Mutable state management.
          </p>

          <div className="space-y-4">
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">State.get(key, default)</h3>
              <p className="text-sm text-muted-foreground mb-2">Get state value.</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`local count = State.get("count", 0)`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">State.set(key, value)</h3>
              <p className="text-sm text-muted-foreground mb-2">Set state value.</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`State.set("count", 10)
State.set("config", {mode = "fast"})`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">State.increment(key, amount)</h3>
              <p className="text-sm text-muted-foreground mb-2">Increment numeric value.</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`State.increment("count")     -- +1
State.increment("count", 5)  -- +5`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">State.append(key, value)</h3>
              <p className="text-sm text-muted-foreground mb-2">Append to array.</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`State.set("items", {})
State.append("items", "first")
State.append("items", "second")`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4 border-b-2 border-primary pb-2">
            Stage Primitives
          </h2>
          <p className="text-muted-foreground mb-4">
            Workflow stage management.
          </p>

          <div className="space-y-4">
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Stage.set(name)</h3>
              <p className="text-sm text-muted-foreground mb-2">Set current stage.</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`Stage.set("processing")`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Stage.current()</h3>
              <p className="text-sm text-muted-foreground mb-2">Get current stage name.</p>
              <p className="text-sm mb-2"><strong>Returns:</strong> String</p>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Stage.is(name)</h3>
              <p className="text-sm text-muted-foreground mb-2">Check if in specific stage.</p>
              <p className="text-sm mb-2"><strong>Returns:</strong> Boolean</p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4 border-b-2 border-primary pb-2">
            Utility Primitives
          </h2>
          <p className="text-muted-foreground mb-4">
            Logging, file operations, and utilities.
          </p>

          <div className="space-y-4">
            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Log.info / warn / error(message, context)</h3>
              <p className="text-sm text-muted-foreground mb-2">Log message at specified level.</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`Log.info("Processing item", {id = item_id})
Log.error("Failed", {error = err})`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Sleep(seconds)</h3>
              <p className="text-sm text-muted-foreground mb-2">Sleep for specified duration.</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`Sleep(5)  -- Wait 5 seconds`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">Json.encode / decode</h3>
              <p className="text-sm text-muted-foreground mb-2">JSON serialization.</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`local json = Json.encode({key = "value"})
local data = Json.decode(json_string)`}</code>
              </pre>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-lg font-mono font-medium mb-2">File.read / write / exists</h3>
              <p className="text-sm text-muted-foreground mb-2">File system operations.</p>
              <pre className="bg-muted rounded p-3 text-sm">
                <code>{`if File.exists("/path/to/file") then
  local content = File.read("/path/to/file")
end`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section className="bg-muted rounded-lg p-6">
          <h2 className="text-2xl font-semibold mb-4">Complete Reference</h2>
          <p className="text-muted-foreground mb-4">
            Full API documentation with all primitives is available in:
          </p>
          <ul className="space-y-2">
            <li>
              <code className="block bg-background px-4 py-2 rounded text-sm">
                /plexus/procedures/docs/api-reference.html
              </code>
            </li>
            <li>
              <code className="block bg-background px-4 py-2 rounded text-sm">
                /plexus/procedures/AGENTS.md
              </code>
            </li>
          </ul>
          <p className="text-muted-foreground mt-4">
            Includes detailed documentation for: Tool, Session, Control, GraphNode primitives and more.
          </p>
        </section>

        <div className="flex gap-4 mt-8">
          <Link href="/documentation/procedures/messages">
            <DocButton>Next: Message Classification →</DocButton>
          </Link>
          <Link href="/documentation/procedures/examples">
            <DocButton variant="outline">← Examples</DocButton>
          </Link>
        </div>
      </div>
    </div>
  )
}

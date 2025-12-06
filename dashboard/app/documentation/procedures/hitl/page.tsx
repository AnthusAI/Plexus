import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"
import { MessageExample, MessageExamples } from "@/components/documentation/message-examples"

export const metadata: Metadata = {
  title: "Human-in-the-Loop - Procedures - Plexus Documentation",
  description: "Master human collaboration patterns with Plexus Procedures"
}

export default function ProceduresHITLPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Human-in-the-Loop (HITL)</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Enable procedures to collaborate with human operators through approval, input, review, and notifications.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Core Principles</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>Blocking by default:</strong> Approval, input, and review operations block workflow execution</li>
            <li><strong>Non-blocking notifications:</strong> Progress updates and alerts don't block execution</li>
            <li><strong>Timeout support:</strong> All blocking operations support timeouts with fallback behavior</li>
            <li><strong>Context-rich:</strong> Provide structured data to help humans make informed decisions</li>
            <li><strong>Stage integration:</strong> Procedure status reflects when waiting for human interaction</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">HITL Primitives</h2>

          <div className="space-y-6">
            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Human.approve()</h3>
              <p className="text-sm text-muted-foreground mb-3">Request yes/no approval (blocking)</p>
              <pre className="bg-muted rounded p-3 text-sm overflow-x-auto">
                <code>{`local approved = Human.approve({
  message = "Deploy to production?",
  context = {
    version = "2.1.0",
    environment = "production",
    changes = change_summary
  },
  timeout = 3600,  -- 1 hour
  default = false
})

if approved then
  deploy()
else
  Log.info("Deployment cancelled")
end`}</code>
              </pre>

              <div className="mt-4">
                <p className="text-xs text-muted-foreground mb-2">How it appears in the chat feed:</p>
                <MessageExample
                  messages={MessageExamples.simpleApproval}
                  height="h-64"
                />
              </div>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Human.input()</h3>
              <p className="text-sm text-muted-foreground mb-3">Request text input (blocking)</p>
              <pre className="bg-muted rounded p-3 text-sm overflow-x-auto">
                <code>{`local topic = Human.input({
  message = "What topic should I research?",
  placeholder = "Enter a topic...",
  timeout = nil  -- Wait forever
})

if topic then
  Procedure.run("researcher", {topic = topic})
end`}</code>
              </pre>

              <div className="mt-4">
                <p className="text-xs text-muted-foreground mb-2">How it appears in the chat feed:</p>
                <MessageExample
                  messages={MessageExamples.inputRequest}
                  height="h-80"
                />
              </div>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Human.review()</h3>
              <p className="text-sm text-muted-foreground mb-3">Request work product review (blocking)</p>
              <pre className="bg-muted rounded p-3 text-sm overflow-x-auto">
                <code>{`local review = Human.review({
  message = "Please review this report",
  artifact = report_content,
  artifact_type = "document",
  options = {"approve", "edit", "reject"},
  timeout = 86400  -- 24 hours
})

if review.decision == "approve" then
  publish(report_content)
elseif review.decision == "edit" then
  publish(review.edited_artifact)
else
  Log.warn("Report rejected")
end`}</code>
              </pre>

              <div className="mt-4">
                <p className="text-xs text-muted-foreground mb-2">How it appears in the chat feed:</p>
                <MessageExample
                  messages={MessageExamples.reviewRequest}
                  height="h-80"
                />
              </div>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Human.notify()</h3>
              <p className="text-sm text-muted-foreground mb-3">Send notification (non-blocking)</p>
              <pre className="bg-muted rounded p-3 text-sm overflow-x-auto">
                <code>{`Human.notify({
  message = "Processing phase 2 of 5",
  level = "info",  -- info, warning, error
  context = {
    progress = "40%",
    items_processed = 200
  }
})

-- Execution continues immediately`}</code>
              </pre>

              <div className="mt-4">
                <p className="text-xs text-muted-foreground mb-2">How progress notifications appear:</p>
                <MessageExample
                  messages={MessageExamples.progressUpdates}
                  height="h-72"
                />
              </div>
            </div>

            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">System.alert()</h3>
              <p className="text-sm text-muted-foreground mb-3">Send system alert (non-blocking)</p>
              <pre className="bg-muted rounded p-3 text-sm overflow-x-auto">
                <code>{`System.alert({
  message = "Memory usage exceeded threshold",
  level = "warning",  -- info, warning, error, critical
  source = "batch_processor",
  context = {
    memory_mb = 8500,
    threshold_mb = 8000
  }
})`}</code>
              </pre>

              <div className="mt-4">
                <p className="text-xs text-muted-foreground mb-2">Alert severity levels:</p>
                <MessageExample
                  messages={MessageExamples.alertLevels}
                  height="h-80"
                />
              </div>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Declarative HITL Points</h2>
          <p className="text-muted-foreground mb-4">
            For predictable workflows, declare HITL points in YAML:
          </p>
          <pre className="bg-muted rounded-lg overflow-x-auto">
            <div className="code-container p-4">
              <code>{`hitl:
  review_content:
    type: review
    message: "Review the generated content"
    timeout: 86400
    options: [approve, edit, reject]

  confirm_publish:
    type: approval
    message: "Publish to production?"
    timeout: 3600
    default: false

workflow: |
  -- Generate content
  Worker.turn()

  -- Use declared review point
  local review = Human.review("review_content", {
    artifact = State.get("content")
  })

  -- Use declared approval point
  if review.decision == "approve" then
    local approved = Human.approve("confirm_publish")
    if approved then
      publish()
    end
  end`}</code>
            </div>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Common Patterns</h2>

          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-2">Pre-Action Approval</h3>
              <p className="text-muted-foreground mb-3">
                Request approval before critical operations:
              </p>
              <pre className="bg-muted rounded-lg overflow-x-auto">
                <div className="code-container p-4">
                  <code>{`workflow: |
  -- Analyze impact
  analyze_impact()

  -- Request approval
  local approved = Human.approve({
    message = "Execute database migration?",
    context = {
      affected_tables = State.get("affected_tables"),
      estimated_duration = "15 minutes",
      rollback_plan = "Available"
    },
    timeout = 1800
  })

  if approved then
    migrate_database()
  end`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Progress with Alerts</h3>
              <p className="text-muted-foreground mb-3">
                Monitor operations and alert on issues:
              </p>
              <pre className="bg-muted rounded-lg overflow-x-auto">
                <div className="code-container p-4">
                  <code>{`workflow: |
  Human.notify({message = "Starting batch job"})

  local processed = 0
  local failed = 0

  for i, item in ipairs(params.items) do
    local ok = process(item)
    if ok then
      processed = processed + 1
    else
      failed = failed + 1
    end

    -- Alert if failure rate too high
    local failure_rate = failed / i
    if failure_rate > 0.1 and i > 10 then
      System.alert({
        message = "High failure rate detected",
        level = "warning",
        source = "batch_processor",
        context = {failure_rate = failure_rate}
      })

      local continue = Human.approve({
        message = "Continue processing?",
        default = false
      })

      if not continue then break end
    end
  end`}</code>
                </div>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Complete Workflow Example</h2>

          <div className="mb-6">
            <p className="text-muted-foreground mb-4">
              Here's how a complete workflow with Human.approve(), notifications, and alerts appears in the chat feed:
            </p>
            <MessageExample
              title="Complete HITL Workflow"
              description="Shows mixed message types: notifications, warnings, approval requests, and responses"
              messages={MessageExamples.completeWorkflow}
              height="h-96"
            />
          </div>

          <h3 className="text-xl font-semibold mb-4 mt-8">Full Procedure Code</h3>
          <pre className="bg-muted rounded-lg overflow-x-auto">
            <div className="code-container p-4">
              <code>{`name: content_pipeline
version: 1.0.0

params:
  topic:
    type: string
    required: true

outputs:
  published:
    type: boolean
    required: true

stages:
  - drafting
  - review
  - publishing

hitl:
  review_content:
    type: review
    message: "Review generated content"
    timeout: 86400

  confirm_publish:
    type: approval
    message: "Publish?"
    timeout: 3600
    default: false

agents:
  writer:
    system_prompt: "Write about: {params.topic}"
    tools: [research, write, done]

workflow: |
  -- Generate
  Stage.set("drafting")
  Human.notify({message = "Generating content"})

  repeat
    Writer.turn()
  until Tool.called("done")

  -- Review
  Stage.set("review")
  local review = Human.review("review_content", {
    artifact = State.get("draft")
  })

  if review.decision == "reject" then
    return {published = false}
  end

  -- Publish
  Stage.set("publishing")
  local approved = Human.approve("confirm_publish")

  if approved then
    publish(review.edited_artifact or State.get("draft"))
    Human.notify({message = "Published successfully"})
    return {published = true}
  else
    return {published = false}
  end`}</code>
            </div>
          </pre>
        </section>

        <div className="flex gap-4 mt-8">
          <Link href="/documentation/procedures/examples">
            <DocButton>Next: Examples & Patterns →</DocButton>
          </Link>
          <Link href="/documentation/procedures/getting-started">
            <DocButton variant="outline">← Getting Started</DocButton>
          </Link>
        </div>
      </div>
    </div>
  )
}

import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"
import { MessageExample } from "@/components/documentation/message-examples"
import { MessageExampleData as MessageExamples } from "@/components/documentation/message-example-data"

export const metadata: Metadata = {
  title: "Message Classification - Procedures - Plexus Documentation",
  description: "Understand message types and visibility in Plexus Procedures"
}

export default function ProceduresMessagesPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Message Classification System</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Every message has a humanInteraction classification that determines visibility and behavior.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Overview</h2>
          <p className="text-muted-foreground mb-4">
            Every message in the Plexus system has a <code>humanInteraction</code> field that determines:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>UI Visibility:</strong> Whether humans see the message</li>
            <li><strong>Blocking Behavior:</strong> Whether execution waits for response</li>
            <li><strong>Response Expected:</strong> Whether human input is required</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Classification Values</h2>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b-2 border-primary">
                  <th className="text-left p-3 font-semibold">Value</th>
                  <th className="text-left p-3 font-semibold">Description</th>
                  <th className="text-left p-3 font-semibold">Blocks?</th>
                  <th className="text-left p-3 font-semibold">UI Visibility</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                <tr className="border-b">
                  <td className="p-3"><code>INTERNAL</code></td>
                  <td className="p-3">Agent reasoning, tool calls</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Hidden</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>CHAT</code></td>
                  <td className="p-3">Human message in conversation</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>CHAT_ASSISTANT</code></td>
                  <td className="p-3">AI response in conversation</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>NOTIFICATION</code></td>
                  <td className="p-3">Workflow progress update</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>ALERT_INFO</code></td>
                  <td className="p-3">System info alert</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible (monitoring)</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>ALERT_WARNING</code></td>
                  <td className="p-3">System warning</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible (monitoring)</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>ALERT_ERROR</code></td>
                  <td className="p-3">System error alert</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible (monitoring)</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>ALERT_CRITICAL</code></td>
                  <td className="p-3">Critical system alert</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible (monitoring)</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>PENDING_APPROVAL</code></td>
                  <td className="p-3">Waiting for yes/no</td>
                  <td className="p-3">Yes</td>
                  <td className="p-3">Visible (action required)</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>PENDING_INPUT</code></td>
                  <td className="p-3">Waiting for input</td>
                  <td className="p-3">Yes</td>
                  <td className="p-3">Visible (action required)</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>PENDING_REVIEW</code></td>
                  <td className="p-3">Waiting for review</td>
                  <td className="p-3">Yes</td>
                  <td className="p-3">Visible (action required)</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>RESPONSE</code></td>
                  <td className="p-3">Human's response</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible</td>
                </tr>
                <tr className="border-b">
                  <td className="p-3"><code>TIMED_OUT</code></td>
                  <td className="p-3">Request expired</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible</td>
                </tr>
                <tr>
                  <td className="p-3"><code>CANCELLED</code></td>
                  <td className="p-3">Request cancelled</td>
                  <td className="p-3">No</td>
                  <td className="p-3">Visible</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Visual Examples</h2>
          <p className="text-muted-foreground mb-6">
            See how different message types appear in the actual chat feed interface:
          </p>

          <div className="space-y-8">
            <div>
              <h3 className="text-xl font-medium mb-3">Procedure Workflow (Mixed Visibility)</h3>
              <p className="text-sm text-muted-foreground mb-3">
                A complete workflow showing notifications, warnings, approval requests, and responses.
                Note: INTERNAL messages (tool calls, agent reasoning) are filtered out in the human UI.
              </p>
              <MessageExample
                title="Optimization Workflow"
                description="Human sees: notifications, alerts, approval requests, and responses"
                messages={MessageExamples.completeWorkflow}
                height="h-96"
              />
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Chat Conversation (All Visible)</h3>
              <p className="text-sm text-muted-foreground mb-3">
                Natural back-and-forth conversation with the AI, including procedure-generated notifications.
              </p>
              <MessageExample
                title="Chat with Procedure Integration"
                description="CHAT messages from user, CHAT_ASSISTANT from AI, plus system NOTIFICATIONS"
                messages={MessageExamples.chatConversation}
                height="h-80"
              />
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">System Monitoring (Alert Stream)</h3>
              <p className="text-sm text-muted-foreground mb-3">
                Severity-based alerts from INFO through CRITICAL with visual color coding.
              </p>
              <MessageExample
                title="Alert Severity Levels"
                description="INFO (blue) → WARNING (yellow) → ERROR (red) → CRITICAL (dark red)"
                messages={MessageExamples.alertLevels}
                height="h-80"
              />
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">UI Filtering</h2>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Human Operator Dashboard</h3>
              <p className="text-sm text-muted-foreground mb-2">Show only user-facing messages:</p>
              <pre className="bg-muted rounded-lg p-4 text-sm">
                <code>{`SELECT * FROM chat_messages
WHERE human_interaction IN (
  'CHAT',
  'CHAT_ASSISTANT',
  'NOTIFICATION',
  'ALERT_WARNING',
  'ALERT_ERROR',
  'ALERT_CRITICAL',
  'PENDING_APPROVAL',
  'PENDING_INPUT',
  'PENDING_REVIEW',
  'RESPONSE'
)`}</code>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Monitoring Dashboard</h3>
              <p className="text-sm text-muted-foreground mb-2">Show only alerts:</p>
              <pre className="bg-muted rounded-lg p-4 text-sm">
                <code>{`SELECT * FROM chat_messages
WHERE human_interaction LIKE 'ALERT_%'
ORDER BY created_at DESC`}</code>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Action Required</h3>
              <p className="text-sm text-muted-foreground mb-2">Show only messages requiring response:</p>
              <pre className="bg-muted rounded-lg p-4 text-sm">
                <code>{`SELECT * FROM chat_messages
WHERE human_interaction IN (
  'PENDING_APPROVAL',
  'PENDING_INPUT',
  'PENDING_REVIEW'
)
AND status = 'pending'`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Design Principles</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>Unified System:</strong> One classification covers all use cases</li>
            <li><strong>Clear Semantics:</strong> Name indicates purpose and behavior</li>
            <li><strong>UI-Friendly:</strong> Easy to filter for different views</li>
            <li><strong>Blocking Explicit:</strong> Clear which messages block workflow</li>
            <li><strong>Monitoring Integration:</strong> Alerts work for both procedures and external systems</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Best Practices</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-green-200 dark:border-green-900 rounded-lg p-4">
              <h3 className="text-lg font-medium mb-2 text-green-700 dark:text-green-300">DO</h3>
              <ul className="list-disc pl-6 space-y-1 text-sm text-muted-foreground">
                <li>Use INTERNAL for agent work</li>
                <li>Use NOTIFICATION for progress</li>
                <li>Use ALERT_* for system events</li>
                <li>Use PENDING_* sparingly</li>
                <li>Use CHAT for conversations</li>
              </ul>
            </div>

            <div className="border border-red-200 dark:border-red-900 rounded-lg p-4">
              <h3 className="text-lg font-medium mb-2 text-red-700 dark:text-red-300">DON'T</h3>
              <ul className="list-disc pl-6 space-y-1 text-sm text-muted-foreground">
                <li>Over-notify (fatigue)</li>
                <li>Mix alerts and notifications</li>
                <li>Block for trivial operations</li>
                <li>Expose internal details</li>
              </ul>
            </div>
          </div>
        </section>

        <section className="bg-muted rounded-lg p-6">
          <h2 className="text-2xl font-semibold mb-4">Complete Documentation</h2>
          <p className="text-muted-foreground mb-4">
            Detailed documentation with examples is available at:
          </p>
          <code className="block bg-background px-4 py-2 rounded text-sm">
            /plexus/procedures/docs/message-classification.html
          </code>
        </section>

        <div className="flex gap-4 mt-8">
          <Link href="/documentation/procedures/spec">
            <DocButton>Next: Technical Spec →</DocButton>
          </Link>
          <Link href="/documentation/procedures/api">
            <DocButton variant="outline">← API Reference</DocButton>
          </Link>
        </div>
      </div>
    </div>
  )
}

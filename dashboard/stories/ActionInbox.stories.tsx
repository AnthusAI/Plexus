import type { Meta, StoryObj } from "@storybook/react"
import { expect, fn, userEvent, within } from "@storybook/test"

import {
  ActionInboxView,
  buildActionInboxViewModel,
  type ActionInboxMessage,
  type ActionUpdate,
} from "@/components/action-inbox"

const pendingMessage: ActionInboxMessage = {
  id: "approval-1",
  accountId: "account-1",
  sessionId: "session-1",
  procedureId: "procedure-1",
  role: "ASSISTANT",
  messageType: "MESSAGE",
  humanInteraction: "PENDING_REVIEW",
  responseStatus: "PENDING",
  content: "Review the prepared change.",
  createdAt: "2026-07-29T16:00:00.000Z",
  metadata: {
    control: {
      request_id: "request-1",
      procedure_id: "procedure-1",
      request_type: "review",
      action_key: "review:run-1",
      title: "Approve the prepared change",
      prompt: "A decision is needed before this run can continue.",
      precondition_fingerprint: "example-fingerprint",
      evidence_fingerprint: "example-evidence-fingerprint",
      preconditions: { run_key: "run-1" },
      expires_at: "2099-07-29T16:00:00.000Z",
      response_schema: {
        type: "object",
        required: ["decision"],
        properties: {
          decision: { enum: ["approve", "reject"] },
          comment: { type: "string" },
        },
      },
      resource_refs: [{ system: "plexus", kind: "report", id: "report-1", label: "Open report" }],
    },
  },
}

const action = buildActionInboxViewModel([pendingMessage], new Date("2026-07-29T17:00:00.000Z")).actions[0]

const update: ActionUpdate = {
  id: "update-1",
  eventKey: "run-1:completed",
  milestone: "COMPLETED",
  severity: "INFO",
  title: "Run completed",
  summary: "The result is ready for review.",
  createdAt: "2026-07-29T15:00:00.000Z",
  resourceRefs: [],
}

const meta = {
  title: "Dashboard/Action Inbox",
  component: ActionInboxView,
  parameters: { layout: "fullscreen" },
  decorators: [(Story) => <div className="h-screen max-w-md bg-frame"><Story /></div>],
  args: {
    actions: [action],
    updates: [update],
    onSubmitResponse: fn().mockResolvedValue(undefined),
  },
} satisfies Meta<typeof ActionInboxView>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const StructuredResponse: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole("radio", { name: "Approve" }))
    await userEvent.click(canvas.getByRole("button", { name: "Submit response" }))
    await expect(args.onSubmitResponse).toHaveBeenCalled()
  },
}

export const NoActions: Story = {
  args: { actions: [], updates: [update] },
}

import React from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import {
  ActionInbox,
  ActionInboxView,
  buildActionInboxViewModel,
  createAmplifyActionInboxDataSource,
  derivePlexusResourceHref,
  type ActionInboxAction,
  type ActionInboxDataSource,
  type ActionInboxMessage,
  type ActionUpdate,
} from "@/components/action-inbox"

const SIMPLE_SCHEMA = {
  type: "object",
  required: ["decision"],
  properties: {
    decision: { enum: ["approve", "reject"] },
    comment: { type: "string" },
  },
}

const PORTFOLIO_SCHEMA = {
  type: "object",
  required: ["decisions"],
  properties: {
    decisions: {
      type: "array",
      minItems: 2,
      maxItems: 2,
      items: {
        type: "object",
        required: ["scorecard_id", "score_id", "decision"],
        properties: {
          scorecard_id: { type: "string" },
          score_id: { type: "string" },
          decision: { enum: ["approve", "reject"] },
          comment: { type: "string" },
        },
      },
    },
  },
}

const message = (overrides: Partial<ActionInboxMessage> = {}): ActionInboxMessage => ({
  id: "pending-1",
  accountId: "account-1",
  sessionId: "session-1",
  procedureId: "procedure-1",
  role: "ASSISTANT",
  messageType: "MESSAGE",
  humanInteraction: "PENDING_REVIEW",
  content: "Review the prepared change.",
  responseStatus: "PENDING",
  createdAt: "2026-07-29T16:00:00.000Z",
  metadata: {
    control: {
      request_id: "request-1",
      procedure_id: "procedure-1",
      request_type: "review",
      action_key: "review:run-1",
      title: "Approve the prepared change",
      prompt: "Review the prepared change.",
      precondition_fingerprint: "fingerprint-1",
      evidence_fingerprint: "evidence-1",
      preconditions: { run_key: "run-1" },
      response_schema: SIMPLE_SCHEMA,
      resource_refs: [{ system: "plexus", kind: "report", id: "report-1", label: "Open report" }],
      expires_at: "2099-07-29T16:00:00.000Z",
    },
  },
  ...overrides,
})

const responseMessage = (overrides: Partial<ActionInboxMessage> = {}): ActionInboxMessage => ({
  id: "response-1",
  accountId: "account-1",
  sessionId: "session-1",
  procedureId: "procedure-1",
  parentMessageId: "pending-1",
  role: "USER",
  messageType: "MESSAGE",
  humanInteraction: "RESPONSE",
  content: JSON.stringify({ value: { decision: "approve" } }),
  createdAt: "2026-07-29T16:01:00.000Z",
  metadata: { control: { value: { decision: "approve" } } },
  ...overrides,
})

const actionFrom = (...messages: ActionInboxMessage[]): ActionInboxAction => {
  const action = buildActionInboxViewModel(messages, new Date("2026-07-29T17:00:00.000Z")).actions[0]
  if (!action) throw new Error("Fixture did not produce an inbox action")
  return action
}

const update = (overrides: Partial<ActionUpdate> = {}): ActionUpdate => ({
  id: "update-1",
  eventKey: "run-1:completed",
  milestone: "COMPLETED",
  severity: "INFO",
  title: "Run completed",
  summary: "The run reached a terminal state.",
  createdAt: "2026-07-29T15:00:00.000Z",
  resourceRefs: [],
  ...overrides,
})

describe("ActionInbox ChatMessage adapter", () => {
  it("forwards account, cursor, and limit to the existing account-createdAt index", async () => {
    const list = jest.fn().mockResolvedValue({ data: [message()], nextToken: "cursor-501" })
    const dataSource = createAmplifyActionInboxDataSource({
      models: { ChatMessage: { listChatMessageByAccountIdAndCreatedAt: list, create: jest.fn() } },
    } as any)

    await expect(dataSource.listMessages({ accountId: "account-1", cursor: "cursor-500", limit: 500 }))
      .resolves.toEqual({ items: [expect.objectContaining({ id: "pending-1" })], nextCursor: "cursor-501" })
    expect(list).toHaveBeenCalledWith(
      { accountId: "account-1", sortDirection: "DESC", limit: 500, nextToken: "cursor-500" },
      expect.objectContaining({ selectionSet: expect.arrayContaining(["responseOwner", "parentMessageId"]) }),
    )
  })

  it("loads account history beyond 500 messages through the same cursor", async () => {
    const listMessages = jest
      .fn()
      .mockResolvedValueOnce({ items: [message()], nextCursor: "cursor-500" })
      .mockResolvedValueOnce({
        items: [message({
          id: "pending-old",
          content: "An older decision",
          metadata: { control: { ...(message().metadata as any).control, title: "An older decision" } },
          createdAt: "2026-07-20T16:00:00.000Z",
        })],
        nextCursor: null,
      })
    const dataSource: ActionInboxDataSource = { listMessages, submitResponse: jest.fn() }

    render(<ActionInbox accountId="account-1" dataSource={dataSource} pageSize={500} />)
    expect(await screen.findByText("Approve the prepared change")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Load older history" }))

    expect(await screen.findByText("An older decision")).toBeInTheDocument()
    expect(listMessages).toHaveBeenLastCalledWith({ accountId: "account-1", cursor: "cursor-500", limit: 500 })
  })

  it("renders the portfolio schema and submits exact target IDs from preconditions", async () => {
    const pending = message({
      metadata: {
        control: {
          ...(message().metadata as any).control,
          response_schema: PORTFOLIO_SCHEMA,
          preconditions: {
            targets: [
              {
                scorecard_id: "scorecard:awkward/1",
                score_id: "score:alpha+1",
                scorecard_name: "Example Portfolio",
                score_name: "First Opportunity",
              },
              {
                scorecard_id: "scorecard:awkward/2",
                score_id: "score:beta+2",
                scorecard_name: "Example Portfolio",
                score_name: "Second Opportunity",
              },
            ],
          },
        },
      },
    })
    const submitResponse = jest.fn().mockResolvedValue(responseMessage())
    const dataSource: ActionInboxDataSource = {
      listMessages: jest.fn().mockResolvedValue({ items: [pending], nextCursor: null }),
      submitResponse,
    }

    render(<ActionInbox accountId="account-1" dataSource={dataSource} />)
    expect(await screen.findByText("First Opportunity")).toBeInTheDocument()
    expect(screen.getAllByText("Example Portfolio")).toHaveLength(2)
    expect(screen.queryByText("score:alpha+1")).not.toBeInTheDocument()
    const firstTarget = screen.getByTestId("portfolio-target-scorecard:awkward/1:score:alpha+1")
    const secondTarget = screen.getByTestId("portfolio-target-scorecard:awkward/2:score:beta+2")
    fireEvent.click(within(firstTarget).getByRole("radio", { name: "Approve" }))
    fireEvent.change(within(firstTarget).getByRole("textbox", { name: "Comment" }), { target: { value: "Ready" } })
    fireEvent.click(within(secondTarget).getByRole("radio", { name: "Reject" }))
    fireEvent.change(within(secondTarget).getByRole("textbox", { name: "Comment" }), { target: { value: "Needs work" } })
    fireEvent.click(screen.getByRole("button", { name: "Submit response" }))

    await waitFor(() => expect(submitResponse).toHaveBeenCalledWith({
      action: expect.objectContaining({ id: "pending-1" }),
      response: {
        decisions: [
          { scorecard_id: "scorecard:awkward/1", score_id: "score:alpha+1", decision: "approve", comment: "Ready" },
          { scorecard_id: "scorecard:awkward/2", score_id: "score:beta+2", decision: "reject", comment: "Needs work" },
        ],
      },
    }))
  })

  it("creates only a canonical child RESPONSE ChatMessage and never dispatches a model", async () => {
    const create = jest.fn().mockResolvedValue({ data: { id: "response-created", createdAt: "2026-07-29T17:00:00.000Z" } })
    const dispatchConsoleChat = jest.fn()
    const client = {
      models: { ChatMessage: { listChatMessageByAccountIdAndCreatedAt: jest.fn(), create } },
      mutations: { dispatchConsoleChat },
    }
    const dataSource = createAmplifyActionInboxDataSource(
      client as any,
      async () => ({ createdByUserId: "user-1" }),
      () => new Date("2026-07-29T17:00:00.000Z"),
    )
    const action = actionFrom(message())

    await dataSource.submitResponse({ action, response: { decision: "approve", comment: "Ready" } })

    expect(create).toHaveBeenCalledTimes(1)
    const input = create.mock.calls[0][0]
    expect(input).toMatchObject({
      accountId: "account-1",
      sessionId: "session-1",
      procedureId: "procedure-1",
      parentMessageId: "pending-1",
      role: "USER",
      messageType: "MESSAGE",
      humanInteraction: "RESPONSE",
      content: JSON.stringify({ value: { decision: "approve", comment: "Ready" } }),
      createdByUserId: "user-1",
      createdAt: "2026-07-29T17:00:00.000Z",
    })
    expect(JSON.parse(input.metadata)).toEqual({
      attribution: { actorType: "user", userId: "user-1" },
      control: {
        request_id: "request-1",
        procedure_id: "procedure-1",
        request_type: "review",
        action_key: "review:run-1",
        precondition_fingerprint: "fingerprint-1",
        evidence_fingerprint: "evidence-1",
        value: { decision: "approve", comment: "Ready" },
        responded_at: "2026-07-29T17:00:00.000Z",
      },
    })
    expect(dispatchConsoleChat).not.toHaveBeenCalled()
  })
})

describe("ActionInbox classification and presentation", () => {
  it("shows duplicate response candidates and identifies the server-accepted child", () => {
    const first = responseMessage()
    const accepted = responseMessage({ id: "response-2", createdAt: "2026-07-29T16:02:00.000Z" })
    const action = actionFrom(message({ responseStatus: "COMPLETED", responseOwner: "response-2" }), first, accepted)

    render(<ActionInboxView actions={[action]} updates={[]} />)

    expect(screen.getByText("2 response candidates")).toBeInTheDocument()
    expect(screen.getByTestId("response-candidate-response-1")).toHaveTextContent("Not accepted")
    expect(screen.getByTestId("response-candidate-response-2")).toHaveTextContent("Accepted")
    expect(screen.getByText("Resolved")).toBeInTheDocument()
  })

  it("derives stale, expired, and cancelled terminal states from parent authority", () => {
    const stale = actionFrom(message({ id: "stale", responseStatus: "FAILED" }))
    const expired = actionFrom(message({
      id: "expired",
      metadata: { control: { ...(message().metadata as any).control, expires_at: "2026-07-29T16:30:00.000Z" } },
    }))
    const timedOut = actionFrom(message({ id: "timed-out", humanInteraction: "TIMED_OUT" }))
    const cancelled = actionFrom(message({ id: "cancelled", humanInteraction: "CANCELLED" }))

    expect([stale.status, expired.status, timedOut.status, cancelled.status]).toEqual([
      "STALE", "EXPIRED", "EXPIRED", "CANCELLED",
    ])
  })

  it("keeps only notification/alert milestones and deduplicates them by event_key", () => {
    const notification = message({
      id: "update-old",
      humanInteraction: "NOTIFICATION",
      metadata: { event_key: "run-1:completed", milestone: "COMPLETED", title: "Old completion" },
      createdAt: "2026-07-29T15:00:00.000Z",
    })
    const latest = message({
      id: "update-latest",
      humanInteraction: "ALERT_INFO",
      metadata: { event_key: "run-1:completed", milestone: "COMPLETED", title: "Latest completion" },
      createdAt: "2026-07-29T15:30:00.000Z",
    })
    const chatter = message({
      id: "progress",
      humanInteraction: "NOTIFICATION",
      metadata: { event_key: "run-1:progress", milestone: "PROGRESS", title: "42% complete" },
    })
    const ordinaryChat = message({
      id: "chat-alert-looking",
      humanInteraction: "CHAT_ASSISTANT",
      metadata: { event_key: "run-1:failed", milestone: "FAILED", title: "Not an update" },
    })

    const view = buildActionInboxViewModel([notification, latest, chatter, ordinaryChat])
    expect(view.updates.map((item) => item.title)).toEqual(["Latest completion"])
  })

  it("renders unsupported response schemas visibly but never as actionable", () => {
    const unsupported = actionFrom(message({
      metadata: {
        control: {
          ...(message().metadata as any).control,
          response_schema: { type: "object", properties: { nested: { type: "object" } } },
        },
      },
    }))

    render(<ActionInboxView actions={[unsupported]} updates={[]} onSubmitResponse={jest.fn()} />)

    expect(screen.getByText("This response schema is not supported by the Action Inbox yet.")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Submit response" })).not.toBeInTheDocument()
  })

  it("orders actions and key milestone updates newest first", () => {
    render(
      <ActionInboxView
        actions={[
          actionFrom(message({ id: "older", createdAt: "2026-07-29T14:00:00.000Z" })),
          actionFrom(message()),
        ]}
        updates={[
          update({ id: "older-update", title: "Earlier completion", createdAt: "2026-07-29T13:00:00.000Z" }),
          update({ id: "latest-update", title: "Latest completion", createdAt: "2026-07-29T15:00:00.000Z" }),
        ]}
      />,
    )

    const actions = screen.getAllByTestId(/^action-inbox-action-/)
    expect(actions.map((element) => element.getAttribute("data-testid"))).toEqual([
      "action-inbox-action-pending-1", "action-inbox-action-older",
    ])
    expect(within(actions[0]).getByRole("link", { name: "Open report" })).toHaveAttribute("href", "/lab/reports/report-1")
  })

  it("derives only supported typed Plexus resource routes", () => {
    expect(derivePlexusResourceHref({ system: "plexus", kind: "score", id: "score-1", scorecardId: "scorecard-1" }))
      .toBe("/lab/scorecards/scorecard-1/scores/score-1")
    expect(derivePlexusResourceHref({ system: "plexus", kind: "report_block", id: "block-1", parentId: "report-1" }))
      .toBe("/lab/reports/report-1")
    expect(derivePlexusResourceHref({ system: "plexus", kind: "score", id: "score-1" })).toBeNull()
    expect(derivePlexusResourceHref({ system: "other", kind: "report", id: "report-1" })).toBeNull()
  })
})

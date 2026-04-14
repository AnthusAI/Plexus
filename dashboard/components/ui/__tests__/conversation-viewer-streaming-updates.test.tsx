import * as React from "react"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"

import ConversationViewer from "../conversation-viewer"

jest.mock("react-virtuoso", () => {
  const React = require("react")
  const Virtuoso = React.forwardRef(function MockVirtuoso(props: any, ref: any) {
    const { data = [], itemContent, components, className } = props
    const Footer = components?.Footer

    React.useImperativeHandle(ref, () => ({
      scrollToIndex: jest.fn(),
    }))

    return (
      <div data-testid="virtuoso-scroller" className={className}>
        {data.map((row: any, index: number) => (
          <div key={row?.id ?? index} data-testid="virtuoso-item">
            {itemContent ? itemContent(index, row) : null}
          </div>
        ))}
        {Footer ? <Footer /> : null}
      </div>
    )
  })

  return { Virtuoso }
})

const mockChatSessionList = jest.fn()
const mockChatMessageList = jest.fn()
const mockChatMessageCreate = jest.fn()
const mockChatSessionOnCreate = jest.fn()
const mockChatMessageOnCreate = jest.fn()
const mockChatMessageOnUpdate = jest.fn()
const mockGraphql = jest.fn()

const mockClient = {
  graphql: mockGraphql,
  models: {
    ChatSession: {
      listChatSessionByProcedureIdAndCreatedAt: mockChatSessionList,
      onCreate: mockChatSessionOnCreate,
    },
    ChatMessage: {
      listChatMessageByProcedureIdAndCreatedAt: mockChatMessageList,
      create: mockChatMessageCreate,
      onCreate: mockChatMessageOnCreate,
      onUpdate: mockChatMessageOnUpdate,
    },
  },
}

jest.mock("@/utils/data-operations", () => ({
  getClient: () => mockClient,
}))

jest.mock("@/components/ai-elements/conversation", () => ({
  Conversation: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ConversationContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AutoScrollToBottom: () => null,
  ConversationEmptyState: ({
    title,
    description,
    icon,
  }: {
    title?: string
    description?: string
    icon?: React.ReactNode
  }) => (
    <div>
      {icon}
      <div>{title}</div>
      <div>{description}</div>
    </div>
  ),
  ConversationScrollButton: () => null,
}))

jest.mock("@/components/ai-elements/prompt-input", () => ({
  PromptInput: ({
    children,
    onSubmit,
  }: {
    children: React.ReactNode
    onSubmit?: ({ text }: { text?: string }) => void
  }) => (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        const textarea = event.currentTarget.querySelector("textarea")
        onSubmit?.({ text: (textarea as HTMLTextAreaElement | null)?.value || "" })
      }}
    >
      {children}
    </form>
  ),
  PromptInputBody: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PromptInputFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PromptInputSubmit: ({ disabled }: { disabled?: boolean }) => (
    <button type="submit" disabled={disabled} aria-label="Submit">
      Submit
    </button>
  ),
  PromptInputTextarea: ({
    value,
    onChange,
    placeholder,
    disabled,
  }: {
    value?: string
    onChange?: (event: React.ChangeEvent<HTMLTextAreaElement>) => void
    placeholder?: string
    disabled?: boolean
  }) => (
    <textarea
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      disabled={disabled}
    />
  ),
}))

jest.mock("@/components/ai-elements/message", () => ({
  Message: ({
    children,
    from,
    ...props
  }: {
    children: React.ReactNode
    from: string
  }) => (
    <div data-role={from} {...props}>
      {children}
    </div>
  ),
  MessageContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

jest.mock("@/components/ai-elements/shimmer", () => ({
  Shimmer: ({ children }: { children?: React.ReactNode }) => <span>{children}</span>,
}))

jest.mock("@/components/ai-elements/tool", () => ({
  Tool: ({ children }: { children: React.ReactNode }) => <div data-testid="tool">{children}</div>,
  ToolHeader: ({
    state,
    toolName,
  }: {
    state: string
    toolName?: string
  }) => <div>{`${toolName || "tool"} ${state}`}</div>,
  ToolContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ToolInput: ({ input }: { input?: unknown }) => <pre>{JSON.stringify(input ?? {})}</pre>,
  ToolOutput: ({
    output,
    errorText,
  }: {
    output?: React.ReactNode
    errorText?: string | null
  }) => <div>{errorText || output}</div>,
}))

if (typeof window !== "undefined" && !("ResizeObserver" in window)) {
  ;(window as any).ResizeObserver = class {
    observe() {}
    disconnect() {}
    unobserve() {}
  }
}

describe("ConversationViewer streaming updates", () => {
  const subscriptions = {
    messageCreate: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
    messageUpdate: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
  }

  beforeEach(() => {
    subscriptions.messageCreate = null
    subscriptions.messageUpdate = null

    mockChatSessionList.mockReset()
    mockChatMessageList.mockReset()
    mockChatMessageCreate.mockReset()
    mockChatSessionOnCreate.mockReset()
    mockChatMessageOnCreate.mockReset()
    mockChatMessageOnUpdate.mockReset()
    mockGraphql.mockReset()

    mockChatSessionList.mockResolvedValue({
      data: [
        {
          id: "sess-1",
          accountId: "acct-1",
          procedureId: "proc-1",
          category: "Console Chat",
          createdAt: "2026-03-27T00:00:00.000Z",
          updatedAt: "2026-03-27T00:00:00.000Z",
        },
      ],
      nextToken: null,
    })

    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-assistant-1",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Hel",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
        },
      ],
      nextToken: null,
    })

    mockChatMessageCreate.mockResolvedValue({
      data: {
        id: "msg-user-2",
        createdAt: "2026-03-27T00:00:02.000Z",
      },
    })

    mockGraphql.mockResolvedValue({
      data: {
        startConsoleRun: {
          accepted: true,
          taskId: "task-1",
          runId: "run-1",
          queuedAt: "2026-03-27T00:00:03.000Z",
        },
      },
    })

    mockChatSessionOnCreate.mockReturnValue({
      subscribe: () => ({ unsubscribe: jest.fn() }),
    })

    mockChatMessageOnCreate.mockReturnValue({
      subscribe: (handlers: { next: (payload: any) => void; error?: (error: Error) => void }) => {
        subscriptions.messageCreate = handlers
        return { unsubscribe: jest.fn() }
      },
    })

    mockChatMessageOnUpdate.mockReturnValue({
      subscribe: (handlers: { next: (payload: any) => void; error?: (error: Error) => void }) => {
        subscriptions.messageUpdate = handlers
        return { unsubscribe: jest.fn() }
      },
    })
  })

  it("updates assistant message in place from onUpdate subscription payloads", async () => {
    const { container } = render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")
    expect(container.querySelectorAll('[data-message-id="msg-assistant-1"]')).toHaveLength(1)

    await act(async () => {
      subscriptions.messageUpdate?.next({
        data: {
          id: "msg-assistant-1",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Hello streaming world",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
          metadata: JSON.stringify({
            streaming: {
              state: "streaming",
            },
          }),
        },
      })
    })

    await waitFor(() => {
      expect(screen.getByText("Hello streaming world")).toBeInTheDocument()
    })
    expect(container.querySelectorAll('[data-message-id="msg-assistant-1"]')).toHaveLength(1)
  })

  it("shows thinking shimmer after send and clears it on first assistant message", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Test thinking state" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
      expect(mockGraphql).toHaveBeenCalled()
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    const dispatchCall = mockGraphql.mock.calls[0]?.[0]
    expect(dispatchCall?.variables?.clientInstrumentation).toBeTruthy()
    const instrumentation = JSON.parse(dispatchCall.variables.clientInstrumentation)
    expect(instrumentation.client_history_snapshot).toEqual([
      { role: "ASSISTANT", content: "Hel" },
      { role: "USER", content: "Test thinking state" },
    ])

    await act(async () => {
      subscriptions.messageCreate?.next({
        data: {
          id: "msg-assistant-2",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Streaming reply",
          createdAt: "2026-03-27T00:00:04.000Z",
          sequenceNumber: 3,
        },
      })
    })

    await waitFor(() => {
      expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
      expect(screen.getByText("Streaming reply")).toBeInTheDocument()
    })
  })

  it("excludes in-progress assistant chunks from client history snapshot", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-assistant-streaming",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Sure! Here’s",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
          metadata: JSON.stringify({
            streaming: {
              state: "streaming",
            },
          }),
        },
      ],
      nextToken: null,
    })

    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Sure! Here’s")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Multiply that by three." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockGraphql).toHaveBeenCalled()
    })

    const dispatchCall = mockGraphql.mock.calls[0]?.[0]
    const instrumentation = JSON.parse(dispatchCall.variables.clientInstrumentation)
    expect(instrumentation.client_history_snapshot).toEqual([
      { role: "USER", content: "Multiply that by three." },
    ])
  })

  it("renders TOOL_CALL and TOOL_RESPONSE as separate Tool components", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-tool-call-1",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "TOOL_CALL",
          humanInteraction: "INTERNAL",
          toolName: "plexus_search",
          toolParameters: JSON.stringify({ query: "console status" }),
          content: "plexus_search(query='console status')",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
        },
        {
          id: "msg-tool-response-1",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "TOOL",
          messageType: "TOOL_RESPONSE",
          humanInteraction: "INTERNAL",
          toolName: "plexus_search",
          toolResponse: JSON.stringify({ result: "ok" }),
          content: "tool response",
          createdAt: "2026-03-27T00:00:02.000Z",
          sequenceNumber: 2,
        },
      ],
      nextToken: null,
    })

    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await waitFor(() => {
      expect(screen.getByText("plexus_search input-available")).toBeInTheDocument()
      expect(screen.getByText("plexus_search output-available")).toBeInTheDocument()
      expect(screen.getAllByTestId("tool")).toHaveLength(2)
    })
  })

  it("keeps USER message before ASSISTANT when timestamps are identical", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-assistant-same-time",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "assistant first in payload",
          createdAt: "2026-03-27T00:00:05.000Z",
        },
        {
          id: "msg-user-same-time",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "USER",
          messageType: "MESSAGE",
          humanInteraction: "CHAT",
          content: "user prompt",
          createdAt: "2026-03-27T00:00:05.000Z",
        },
      ],
      nextToken: null,
    })

    const { container } = render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("user prompt")
    await screen.findByText("assistant first in payload")

    const messageNodes = container.querySelectorAll("[data-message-id]")
    const orderedIds = Array.from(messageNodes).map((node) => node.getAttribute("data-message-id"))
    const userIndex = orderedIds.indexOf("msg-user-same-time")
    const assistantIndex = orderedIds.indexOf("msg-assistant-same-time")

    expect(userIndex).toBeGreaterThanOrEqual(0)
    expect(assistantIndex).toBeGreaterThanOrEqual(0)
    expect(userIndex).toBeLessThan(assistantIndex)
  })
})

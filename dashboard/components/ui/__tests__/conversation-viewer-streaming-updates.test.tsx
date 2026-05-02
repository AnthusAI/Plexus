import * as React from "react"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"

import ConversationViewer from "../conversation-viewer"

const mockScrollToIndex = jest.fn()
const atBottomCallbacks: Array<(isAtBottom: boolean) => void> = []

jest.mock("../evaluation-tool-output", () => ({
  __esModule: true,
  default: ({ toolOutput }: { toolOutput: unknown }) => (
    <div data-testid="evaluation-tool-output">{JSON.stringify(toolOutput)}</div>
  ),
}))

jest.mock("react-virtuoso", () => {
  const React = require("react")
  const Virtuoso = React.forwardRef(function MockVirtuoso(props: any, ref: any) {
    const { data = [], itemContent, components, className, atBottomStateChange } = props
    const Footer = components?.Footer

    React.useImperativeHandle(ref, () => ({
      scrollToIndex: mockScrollToIndex,
    }))

    React.useEffect(() => {
      if (!atBottomStateChange) {
        return
      }
      atBottomCallbacks.push(atBottomStateChange)
      atBottomStateChange(true)
      return () => {
        const idx = atBottomCallbacks.indexOf(atBottomStateChange)
        if (idx >= 0) {
          atBottomCallbacks.splice(idx, 1)
        }
      }
    }, [atBottomStateChange])

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
const mockChatSessionGet = jest.fn()
const mockChatMessageList = jest.fn()
const mockChatMessageCreate = jest.fn()
const mockChatSessionOnCreate = jest.fn()
const mockChatSessionOnUpdate = jest.fn()
const mockChatMessageOnCreate = jest.fn()
const mockChatMessageOnUpdate = jest.fn()
const mockGraphql = jest.fn()

const mockClient = {
  graphql: mockGraphql,
  models: {
    ChatSession: {
      listChatSessionByProcedureIdAndCreatedAt: mockChatSessionList,
      get: mockChatSessionGet,
      onCreate: mockChatSessionOnCreate,
      onUpdate: mockChatSessionOnUpdate,
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
  PromptInputSelect: ({
    children,
    onValueChange,
    disabled,
  }: {
    children: React.ReactNode
    onValueChange?: (value: string) => void
    disabled?: boolean
  }) => (
    <div data-disabled={disabled}>
      <button
        type="button"
        aria-label="Select GPT-5.3"
        onClick={() => onValueChange?.("gpt-5.3")}
      >
        Select GPT-5.3
      </button>
      {children}
    </div>
  ),
  PromptInputSelectTrigger: ({ children }: { children: React.ReactNode }) => <button type="button">{children}</button>,
  PromptInputSelectValue: ({ placeholder }: { placeholder?: string }) => <>{placeholder}</>,
  PromptInputSelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  PromptInputSelectItem: ({
    children,
    value: _value,
  }: {
    children: React.ReactNode
    value: string
  }) => <div>{children}</div>,
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
    sessionUpdate: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
    messageCreate: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
    messageUpdate: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
  }

  beforeEach(() => {
    mockScrollToIndex.mockReset()
    atBottomCallbacks.length = 0
    subscriptions.sessionUpdate = null
    subscriptions.messageCreate = null
    subscriptions.messageUpdate = null

    mockChatSessionList.mockReset()
    mockChatMessageList.mockReset()
    mockChatMessageCreate.mockReset()
    mockChatSessionGet.mockReset()
    mockChatSessionOnCreate.mockReset()
    mockChatSessionOnUpdate.mockReset()
    mockChatMessageOnCreate.mockReset()
    mockChatMessageOnUpdate.mockReset()
    mockGraphql.mockReset()
    delete process.env.NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET

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
    mockChatSessionGet.mockResolvedValue({ data: null })

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

    mockChatSessionOnCreate.mockReturnValue({
      subscribe: () => ({ unsubscribe: jest.fn() }),
    })
    mockChatSessionOnUpdate.mockReturnValue({
      subscribe: (handlers: { next: (payload: any) => void; error?: (error: Error) => void }) => {
        subscriptions.sessionUpdate = handlers
        return { unsubscribe: jest.fn() }
      },
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

  const emitAtBottomState = (isAtBottom: boolean) => {
    for (const callback of [...atBottomCallbacks]) {
      callback(isAtBottom)
    }
  }

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

  it("auto-follows conversation when streaming updates arrive", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")
    mockScrollToIndex.mockClear()

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
      expect(mockScrollToIndex).toHaveBeenCalledWith(
        expect.objectContaining({
          index: "LAST",
          align: "end",
          behavior: "auto",
        })
      )
    })
  })

  it("auto-follows when a tool call arrives while at bottom", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")
    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Run a tool" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
    })
    mockScrollToIndex.mockClear()

    await act(async () => {
      subscriptions.messageCreate?.next({
        data: {
          id: "msg-tool-call-1",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "TOOL_CALL",
          humanInteraction: "INTERNAL",
          content: "Tool call: execute_tactus",
          createdAt: "2026-03-27T00:00:02.000Z",
          sequenceNumber: 2,
        },
      })
    })

    await waitFor(() => {
      expect(mockScrollToIndex).toHaveBeenCalledWith(
        expect.objectContaining({
          index: "LAST",
          align: "end",
          behavior: "auto",
        })
      )
    })
  })

  it("does not auto-follow tool activity after user scrolls up", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")
    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Run a tool" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
    })
    mockScrollToIndex.mockClear()

    await act(async () => {
      emitAtBottomState(false)
    })

    await act(async () => {
      subscriptions.messageCreate?.next({
        data: {
          id: "msg-tool-call-2",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "TOOL_CALL",
          humanInteraction: "INTERNAL",
          content: "Tool call: execute_tactus",
          createdAt: "2026-03-27T00:00:02.000Z",
          sequenceNumber: 2,
        },
      })
    })

    await waitFor(() => {
      expect(mockScrollToIndex).not.toHaveBeenCalled()
    })

    await act(async () => {
      emitAtBottomState(true)
    })

    await act(async () => {
      subscriptions.messageUpdate?.next({
        data: {
          id: "msg-tool-call-2",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "TOOL_RESPONSE",
          humanInteraction: "INTERNAL",
          content: "Tool output",
          createdAt: "2026-03-27T00:00:03.000Z",
          sequenceNumber: 3,
        },
      })
    })

    await waitFor(() => {
      expect(mockScrollToIndex).toHaveBeenCalledWith(
        expect.objectContaining({
          index: "LAST",
          align: "end",
          behavior: "auto",
        })
      )
    })
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
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    const messageCreateCall = mockChatMessageCreate.mock.calls[0] || []
    expect(messageCreateCall[1]).toBeUndefined()
    const createdMessage = messageCreateCall[0]
    expect(createdMessage.responseTarget).toBe("cloud")
    expect(createdMessage.responseStatus).toBe("PENDING")
    const metadata = JSON.parse(createdMessage.metadata)
    expect(metadata.instrumentation.client_history_snapshot).toEqual([
      { role: "ASSISTANT", content: "Hel" },
      { role: "USER", content: "Test thinking state" },
    ])
    expect(mockGraphql).not.toHaveBeenCalled()

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
      expect(mockChatMessageCreate).toHaveBeenCalled()
    })

    const createdMessage = mockChatMessageCreate.mock.calls[0]?.[0]
    const metadata = JSON.parse(createdMessage.metadata)
    expect(metadata.instrumentation.client_history_snapshot).toEqual([
      { role: "USER", content: "Multiply that by three." },
    ])
  })

  it("uses local response target from environment when creating a user message", async () => {
    process.env.NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET = "local:ryan"

    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Use my local worker." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
    })

    const createdMessage = mockChatMessageCreate.mock.calls[0]?.[0]
    expect(createdMessage.responseTarget).toBe("local:ryan")
    expect(createdMessage.responseStatus).toBe("PENDING")
    const metadata = JSON.parse(createdMessage.metadata)
    expect(metadata.model.id).toBe("gpt-5.4-mini")
    expect(metadata.instrumentation.client_selected_model).toBe("gpt-5.4-mini")
    expect(mockGraphql).not.toHaveBeenCalled()
  })

  it("saves procedure steering messages without console dispatch behavior", async () => {
    render(
      <ConversationViewer
        procedureId="proc-1"
        defaultSidebarCollapsed={false}
        enableProcedureSteering={true}
      />
    )

    await screen.findByText("Hel")
    expect(screen.queryByText("Model")).not.toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Focus the final summary on reviewer contradictions." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
    })

    const createdMessage = mockChatMessageCreate.mock.calls[0]?.[0]
    expect(createdMessage.role).toBe("USER")
    expect(createdMessage.humanInteraction).toBe("CHAT")
    expect(createdMessage.messageType).toBe("MESSAGE")
    expect(createdMessage.responseTarget).toBe("proc-1")
    expect(createdMessage.responseStatus).toBe("COMPLETED")
    const metadata = JSON.parse(createdMessage.metadata)
    expect(metadata).toEqual({
      source: "procedure-steering-input",
      scope: "all_agents",
      sent_at: expect.any(String),
    })
    expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
    expect(mockGraphql).not.toHaveBeenCalled()
  })

  it("writes non-default selected model into outgoing metadata", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")
    fireEvent.click(screen.getByRole("button", { name: "Select GPT-5.3" }))

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Route this with GPT-5.3." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
    })

    const createdMessage = mockChatMessageCreate.mock.calls[0]?.[0]
    const metadata = JSON.parse(createdMessage.metadata)
    expect(metadata.model.id).toBe("gpt-5.3")
    expect(metadata.instrumentation.client_selected_model).toBe("gpt-5.3")
  })

  it("reveals hidden-until-named sessions after session update notifications", async () => {
    let currentSessionRows = [
      {
        id: "sess-hidden",
        accountId: "acct-1",
        procedureId: "proc-1",
        category: "Optimize",
        metadata: JSON.stringify({ console: { hidden_until_named: true } }),
        createdAt: "2026-03-27T00:00:00.000Z",
        updatedAt: "2026-03-27T00:00:00.000Z",
      },
    ]
    mockChatSessionList.mockImplementation(async () => ({
      data: currentSessionRows,
      nextToken: null,
    }))

    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await waitFor(() => {
      expect(screen.getByText("Chat Sessions (0)")).toBeInTheDocument()
    })

    currentSessionRows = [
      {
        id: "sess-hidden",
        accountId: "acct-1",
        procedureId: "proc-1",
        name: "Coverage Session",
        category: "Optimize",
        metadata: JSON.stringify({ console: { hidden_until_named: false } }),
        createdAt: "2026-03-27T00:00:00.000Z",
        updatedAt: "2026-03-27T00:00:30.000Z",
      },
    ]

    await act(async () => {
      subscriptions.sessionUpdate?.next({ data: { id: "sess-hidden" } })
    })

    await waitFor(() => {
      expect(screen.getByText("Chat Sessions (1)")).toBeInTheDocument()
      expect(screen.getAllByText("Coverage Session").length).toBeGreaterThan(0)
    })
  })

  it("clears selection instead of auto-selecting a different session when active session disappears", async () => {
    let currentSessionRows = [
      {
        id: "sess-1",
        accountId: "acct-1",
        procedureId: "proc-1",
        name: "Current Session",
        category: "Optimize",
        createdAt: "2026-03-27T00:00:00.000Z",
        updatedAt: "2026-03-27T00:00:00.000Z",
      },
    ]
    mockChatSessionList.mockImplementation(async () => ({
      data: currentSessionRows,
      nextToken: null,
    }))

    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await waitFor(() => {
      expect(screen.getAllByText("Current Session").length).toBeGreaterThan(0)
    })

    currentSessionRows = [
      {
        id: "sess-2",
        accountId: "acct-1",
        procedureId: "proc-1",
        name: "Different Session",
        category: "Optimize",
        createdAt: "2026-03-27T00:01:00.000Z",
        updatedAt: "2026-03-27T00:01:00.000Z",
      },
    ]

    await act(async () => {
      subscriptions.sessionUpdate?.next({ data: { id: "sess-2" } })
    })

    await waitFor(() => {
      expect(screen.getByText("No session selected")).toBeInTheDocument()
      expect(screen.getByText("Chat Sessions (1)")).toBeInTheDocument()
      expect(screen.queryByText("Different Session")).toBeInTheDocument()
    })
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

  it("renders execute_tactus evaluation envelopes using EvaluationToolOutput", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-exec-tactus-eval",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "TOOL_CALL",
          humanInteraction: "INTERNAL",
          toolName: "execute_tactus",
          toolParameters: JSON.stringify({ tactus: "evaluate{ scorecard = 'X', score = 'Y' }" }),
          toolResponse: JSON.stringify({
            ok: true,
            api_calls: ["plexus.evaluation.run"],
            value: { evaluation_id: "eval-1" },
          }),
          content: "execute_tactus(...)",
          createdAt: "2026-03-27T00:00:03.000Z",
          sequenceNumber: 3,
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
      expect(screen.getByTestId("evaluation-tool-output")).toBeInTheDocument()
      expect(screen.getByTestId("evaluation-tool-output").textContent).toContain("eval-1")
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

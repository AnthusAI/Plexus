import * as React from "react"
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react"

import ConversationViewer from "../conversation-viewer"

jest.mock("@monaco-editor/react", () => ({
  DiffEditor: ({ language, original, modified }: any) => (
    <div data-testid={`diff-editor-${language}`} data-original={original} data-modified={modified} />
  ),
}))

const mockScrollToIndex = jest.fn()
let latestVirtuosoProps: any = null

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
    const Scroller = components?.Scroller || "div"
    latestVirtuosoProps = props

    React.useImperativeHandle(ref, () => ({
      scrollToIndex: mockScrollToIndex,
    }))

    React.useEffect(() => {
      atBottomStateChange?.(true)
    }, [atBottomStateChange, data.length])

    return (
      <Scroller data-testid="virtuoso-scroller" className={className}>
        {data.map((row: any, index: number) => (
          <div key={row?.id ?? index} data-testid="virtuoso-item">
            {itemContent ? itemContent(index, row) : null}
          </div>
        ))}
        {Footer ? <Footer /> : null}
      </Scroller>
    )
  })

  return { Virtuoso }
})

const mockChatSessionList = jest.fn()
const mockChatSessionGet = jest.fn()
const mockChatMessageList = jest.fn()
const mockChatMessageListBySession = jest.fn()
const mockChatMessageGet = jest.fn()
const mockChatMessageCreate = jest.fn()
const mockChatSessionOnCreate = jest.fn()
const mockChatSessionOnUpdate = jest.fn()
const mockChatSessionOnDelete = jest.fn()
const mockChatMessageOnCreate = jest.fn()
const mockChatMessageOnUpdate = jest.fn()
const mockChatMessageOnDelete = jest.fn()
const mockUserGet = jest.fn()
const mockGraphql = jest.fn()

const mockClient = {
  graphql: mockGraphql,
  models: {
    ChatSession: {
      listChatSessionByProcedureIdAndCreatedAt: mockChatSessionList,
      get: mockChatSessionGet,
      onCreate: mockChatSessionOnCreate,
      onUpdate: mockChatSessionOnUpdate,
      onDelete: mockChatSessionOnDelete,
    },
    ChatMessage: {
      listChatMessageByProcedureIdAndCreatedAt: mockChatMessageList,
      listChatMessageBySessionIdAndCreatedAt: mockChatMessageListBySession,
      get: mockChatMessageGet,
      create: mockChatMessageCreate,
      onCreate: mockChatMessageOnCreate,
      onUpdate: mockChatMessageOnUpdate,
      onDelete: mockChatMessageOnDelete,
    },
    User: {
      get: mockUserGet,
    },
  },
}

jest.mock("@/utils/data-operations", () => ({
  getClient: () => mockClient,
}))

jest.mock("@/utils/user-profile", () => ({
  getCurrentUserAttribution: jest.fn().mockResolvedValue({ createdByUserId: "user-1" }),
  gravatarAvatarUrl: jest.fn(async (email: string, size = 64) => (
    `https://www.gravatar.com/avatar/test?s=${size}&email=${encodeURIComponent(email)}`
  )),
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
  MessageContent: ({
    children,
    className,
  }: {
    children: React.ReactNode
    className?: string
  }) => <div data-testid="message-content" className={className}>{children}</div>,
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
    sessionCreate: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
    sessionUpdate: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
    sessionDelete: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
    messageCreate: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
    messageUpdate: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
    messageDelete: null as null | { next: (payload: any) => void; error?: (error: Error) => void },
  }

  beforeEach(() => {
    mockScrollToIndex.mockReset()
    latestVirtuosoProps = null
    subscriptions.sessionCreate = null
    subscriptions.sessionUpdate = null
    subscriptions.sessionDelete = null
    subscriptions.messageCreate = null
    subscriptions.messageUpdate = null
    subscriptions.messageDelete = null

    mockChatSessionList.mockReset()
    mockChatMessageList.mockReset()
    mockChatMessageListBySession.mockReset()
    mockChatMessageGet.mockReset()
    mockChatMessageCreate.mockReset()
    mockChatSessionGet.mockReset()
    mockChatSessionOnCreate.mockReset()
    mockChatSessionOnUpdate.mockReset()
    mockChatSessionOnDelete.mockReset()
    mockChatMessageOnCreate.mockReset()
    mockChatMessageOnUpdate.mockReset()
    mockChatMessageOnDelete.mockReset()
    mockUserGet.mockReset()
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
    mockChatMessageListBySession.mockResolvedValue({
      data: [],
      nextToken: null,
    })
    mockChatMessageGet.mockResolvedValue({
      data: {
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
    })

    mockChatMessageCreate.mockResolvedValue({
      data: {
        id: "msg-user-2",
        createdAt: "2026-03-27T00:00:02.000Z",
      },
    })

    mockChatSessionOnCreate.mockReturnValue({
      subscribe: (handlers: { next: (payload: any) => void; error?: (error: Error) => void }) => {
        subscriptions.sessionCreate = handlers
        return { unsubscribe: jest.fn() }
      },
    })
    mockChatSessionOnUpdate.mockReturnValue({
      subscribe: (handlers: { next: (payload: any) => void; error?: (error: Error) => void }) => {
        subscriptions.sessionUpdate = handlers
        return { unsubscribe: jest.fn() }
      },
    })
    mockChatSessionOnDelete.mockReturnValue({
      subscribe: (handlers: { next: (payload: any) => void; error?: (error: Error) => void }) => {
        subscriptions.sessionDelete = handlers
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
    mockChatMessageOnDelete.mockReturnValue({
      subscribe: (handlers: { next: (payload: any) => void; error?: (error: Error) => void }) => {
        subscriptions.messageDelete = handlers
        return { unsubscribe: jest.fn() }
      },
    })

    mockUserGet.mockResolvedValue({
      data: {
        id: "user-1",
        email: "author@example.com",
        displayName: "Author Person",
      },
    })
  })

  it("hydrates selected session messages when session update is newer than loaded visible messages", async () => {
    mockChatSessionList.mockResolvedValueOnce({
      data: [
        {
          id: "sess-1",
          accountId: "acct-1",
          procedureId: "proc-1",
          category: "Console Chat",
          createdAt: "2026-03-27T00:00:00.000Z",
          updatedAt: "2026-03-27T00:00:05.000Z",
        },
      ],
      nextToken: null,
    })
    mockChatMessageList.mockResolvedValueOnce({
      data: [
        {
          id: "msg-user-stale",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "USER",
          messageType: "MESSAGE",
          humanInteraction: "CHAT",
          content: "Reply with pong",
          createdAt: "2026-03-27T00:00:02.000Z",
        },
      ],
      nextToken: null,
    })
    mockChatMessageListBySession.mockResolvedValueOnce({
      data: [
        {
          id: "msg-user-stale",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "USER",
          messageType: "MESSAGE",
          humanInteraction: "CHAT",
          content: "Reply with pong",
          createdAt: "2026-03-27T00:00:02.000Z",
        },
        {
          id: "msg-assistant-hydrated",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "pong",
          createdAt: "2026-03-27T00:00:04.000Z",
          sequenceNumber: 3,
          metadata: JSON.stringify({
            streaming: {
              state: "complete",
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

    expect(await screen.findByText("pong")).toBeInTheDocument()
    expect(mockChatMessageListBySession).toHaveBeenCalledWith(
      expect.objectContaining({
        sessionId: "sess-1",
        sortDirection: "ASC",
      }),
      expect.objectContaining({
        selectionSet: expect.arrayContaining(["id", "sessionId", "content"]),
      }),
    )
  })

  it("updates assistant message in place from onUpdate subscription payloads", async () => {
    const { container } = render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByPlaceholderText("Type a message")
    expect(container.querySelectorAll('[data-message-id="msg-assistant-1"]')).toHaveLength(1)
    for (const call of mockChatMessageList.mock.calls) {
      expect(call[1]?.selectionSet || []).not.toContain("createdByUserId")
    }

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

  it("renders user avatars from loaded metadata attribution without selecting createdByUserId", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-user-1",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "USER",
          messageType: "MESSAGE",
          humanInteraction: "CHAT",
          content: "human message",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
          metadata: JSON.stringify({
            attribution: {
              actorType: "user",
              userId: "user-1",
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

    expect(await screen.findByLabelText("Message author: author@example.com")).toBeInTheDocument()
    for (const call of mockChatMessageList.mock.calls) {
      expect(call[1]?.selectionSet || []).not.toContain("createdByUserId")
    }
  })

  it("ignores regressive assistant streaming updates that arrive out of order", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByPlaceholderText("Type a message")

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
          content: "Hello",
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

    expect(screen.getByText("Hello streaming world")).toBeInTheDocument()
    expect(screen.queryByText("Hello")).not.toBeInTheDocument()
  })

  it("auto-follows conversation when streaming updates arrive", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByPlaceholderText("Type a message")
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

  it("keeps auto-follow pinned through final completion layout changes", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByPlaceholderText("Type a message")
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
          content: "Final completed response",
          responseStatus: "COMPLETED",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
          metadata: JSON.stringify({
            streaming: {
              state: "complete",
            },
          }),
        },
      })
    })

    await waitFor(() => {
      expect(mockScrollToIndex.mock.calls.length).toBeGreaterThanOrEqual(2)
    })
    expect(latestVirtuosoProps?.followOutput(false)).toBe("auto")
  })

  it("renders assistant markdown responses with visible overflow and indented lists", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-assistant-markdown",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Plain assistant text\n\n_Italic response_\n\n- Bullet item\n1. Numbered item",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
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

    let messageContent: Element | null = null
    await waitFor(() => {
      messageContent = container.querySelector('[data-message-id="msg-assistant-markdown"] [data-testid="message-content"]')
      expect(messageContent).not.toBeNull()
    })
    expect(messageContent).toHaveTextContent("Plain assistant text")
    expect(messageContent).toHaveTextContent("Italic response")
    expect(messageContent).toHaveTextContent("Bullet item")
    expect(messageContent).toHaveTextContent("Numbered item")
    expect(messageContent).toHaveClass("overflow-visible")
    expect(messageContent).toHaveClass("px-1")
    expect(messageContent).not.toHaveClass("overflow-hidden")
  })

  it("shows assistant cost badges for completed responses and a fallback when cost is unavailable", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-assistant-cost",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Costed response",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
          metadata: JSON.stringify({
            streaming: {
              state: "complete",
            },
            cost: {
              billing_mode: "spent",
              summary: {
                total_usd: "0.0021",
                llm_calls: "1",
                prompt_tokens: "120",
                completion_tokens: "30",
                total_tokens: "150",
              },
            },
          }),
        },
        {
          id: "msg-assistant-no-cost",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "No cost metadata response",
          createdAt: "2026-03-27T00:00:02.000Z",
          sequenceNumber: 2,
          metadata: JSON.stringify({
            streaming: {
              state: "complete",
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

    const spentBadges = await screen.findAllByText("Spent $0.0021")
    expect(spentBadges.length).toBeGreaterThan(0)
    await screen.findByText("Cost unavailable")
  })

  it("renders streaming assistant chunks as plain text until completion", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-assistant-streaming-markdown",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "_Still streaming_",
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

    const { container } = render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await waitFor(() => {
      const messageContent = container.querySelector(
        '[data-message-id="msg-assistant-streaming-markdown"] [data-testid="message-content"]'
      )
      expect(messageContent).not.toBeNull()
      expect(messageContent?.textContent).toContain("_Still streaming_")
    })
  })

  it("pauses auto-follow after an upward user scroll and resumes at the bottom", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    const scroller = await screen.findByTestId("virtuoso-scroller")
    Object.defineProperties(scroller, {
      scrollTop: { configurable: true, writable: true, value: 500 },
      scrollHeight: { configurable: true, value: 1200 },
      clientHeight: { configurable: true, value: 400 },
    })

    fireEvent.scroll(scroller)
    fireEvent.wheel(scroller, { deltaY: -120 })
    Object.defineProperty(scroller, "scrollTop", { configurable: true, writable: true, value: 300 })
    fireEvent.scroll(scroller)

    await waitFor(() => {
      expect(latestVirtuosoProps?.followOutput(false)).toBe(false)
    })

    Object.defineProperty(scroller, "scrollTop", { configurable: true, writable: true, value: 800 })
    fireEvent.scroll(scroller)

    await waitFor(() => {
      expect(latestVirtuosoProps?.followOutput(false)).toBe("auto")
    })
  })

  it("shows thinking shimmer after send and clears it on first assistant message", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByPlaceholderText("Type a message")

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
    expect(metadata.attribution).toEqual({
      actorType: "user",
      userId: "user-1",
    })
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

  it("does not clear thinking when only a stale assistant update arrives", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByPlaceholderText("Type a message")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Test stale update handling" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

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
          content: "Older assistant update",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
        },
      })
    })

    expect(screen.getByText("Thinking")).toBeInTheDocument()

    await act(async () => {
      subscriptions.messageCreate?.next({
        data: {
          id: "msg-assistant-new",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Fresh assistant reply",
          createdAt: "2099-03-27T00:00:04.000Z",
          sequenceNumber: 3,
        },
      })
    })

    await waitFor(() => {
      expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
      expect(screen.getByText("Fresh assistant reply")).toBeInTheDocument()
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

    await screen.findByPlaceholderText("Type a message")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Use my local worker." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
    })

    const createdMessage = mockChatMessageCreate.mock.calls[0]?.[0]
    expect(createdMessage.createdByUserId).toBe("user-1")
    expect(createdMessage.responseTarget).toBe("local:ryan")
    expect(createdMessage.responseStatus).toBe("PENDING")
    const metadata = JSON.parse(createdMessage.metadata)
    expect(metadata.attribution).toEqual({
      actorType: "user",
      userId: "user-1",
    })
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

    await screen.findByPlaceholderText("Type a message")

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
    expect(JSON.parse(createdMessage.metadata)).toEqual({
      attribution: {
        actorType: "user",
        userId: "user-1",
      },
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

    await screen.findByPlaceholderText("Type a message")
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
      subscriptions.sessionUpdate?.next({
        data: {
          onUpdateChatSession: currentSessionRows[0],
        },
      })
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

    await act(async () => {
      subscriptions.sessionCreate?.next({
        data: {
          onCreateChatSession: {
            id: "sess-2",
            accountId: "acct-1",
            procedureId: "proc-1",
            name: "Different Session",
            category: "Optimize",
            createdAt: "2026-03-27T00:01:00.000Z",
            updatedAt: "2026-03-27T00:01:00.000Z",
          },
        },
      })
      subscriptions.sessionDelete?.next({
        data: {
          onDeleteChatSession: { id: "sess-1", procedureId: "proc-1" },
        },
      })
    })

    await waitFor(() => {
      expect(screen.getByText("No session selected")).toBeInTheDocument()
      expect(screen.getByText("Chat Sessions (1)")).toBeInTheDocument()
      expect(screen.queryByText("Different Session")).toBeInTheDocument()
    })
  })

  it("hydrates malformed message subscription payloads without polling", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")
    const initialSessionListCalls = mockChatSessionList.mock.calls.length
    const initialMessageListCalls = mockChatMessageList.mock.calls.length

    mockChatMessageGet.mockResolvedValueOnce({
      data: {
        id: "msg-assistant-1",
        accountId: "acct-1",
        procedureId: "proc-1",
        sessionId: "sess-1",
        role: "ASSISTANT",
        messageType: "MESSAGE",
        humanInteraction: "CHAT_ASSISTANT",
        content: "Hello hydrated",
        createdAt: "2026-03-27T00:00:01.000Z",
        sequenceNumber: 1,
      },
    })

    await act(async () => {
      subscriptions.sessionUpdate?.next({ data: { onUpdateChatSession: { id: "sess-1" } } })
      subscriptions.messageUpdate?.next({ data: { onUpdateChatMessage: { id: "msg-assistant-1" } } })
    })

    await waitFor(() => {
      expect(mockChatSessionList).toHaveBeenCalledTimes(initialSessionListCalls)
      expect(mockChatMessageList).toHaveBeenCalledTimes(initialMessageListCalls)
      expect(mockChatMessageGet).toHaveBeenCalledTimes(1)
      expect(screen.getByText("Hello hydrated")).toBeInTheDocument()
    })
  })

  it("reconciles pending thinking state when terminal user update arrives but assistant event is missed", async () => {
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Test reconcile path" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    mockChatMessageListBySession.mockResolvedValueOnce({
      data: [
        {
          id: "msg-assistant-recovered",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Recovered assistant response",
          createdAt: "2099-03-27T00:00:04.000Z",
          sequenceNumber: 3,
          metadata: JSON.stringify({
            streaming: {
              state: "complete",
            },
          }),
        },
      ],
      nextToken: null,
    })

    await act(async () => {
      subscriptions.messageUpdate?.next({
        data: {
          id: "msg-user-2",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "USER",
          messageType: "MESSAGE",
          humanInteraction: "CHAT",
          content: "Test reconcile path",
          createdAt: "2099-03-27T00:00:02.000Z",
          responseStatus: "COMPLETED",
          responseCompletedAt: "2099-03-27T00:00:05.000Z",
          sequenceNumber: 2,
        },
      })
    })

    await waitFor(() => {
      expect(mockChatMessageListBySession).toHaveBeenCalled()
      expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
    })
  })

  it("reconciles pending thinking state after timeout when no terminal status update arrives", async () => {
    mockChatMessageCreate.mockResolvedValueOnce({
      data: {
        id: "msg-user-timeout",
        createdAt: "2000-01-01T00:00:00.000Z",
      },
    })

    mockChatMessageListBySession.mockResolvedValueOnce({
      data: [
        {
          id: "msg-assistant-timeout-recovered",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Recovered after timeout reconcile",
          createdAt: "2099-03-27T00:00:04.000Z",
          sequenceNumber: 3,
          metadata: JSON.stringify({
            streaming: {
              state: "complete",
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

    await screen.findByText("Hel")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Test timeout reconcile path" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(mockChatMessageListBySession).toHaveBeenCalledTimes(1)
      expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
      expect(screen.getByText("Recovered after timeout reconcile")).toBeInTheDocument()
    })
  })

  it("schedules pending assistant reconciliation at about 500ms instead of the old 30s reconcile delay", async () => {
    const timeoutSpy = jest.spyOn(global, "setTimeout")
    const createdAt = new Date().toISOString()
    mockChatMessageCreate.mockResolvedValueOnce({
      data: {
        id: "msg-user-fast-timeout",
        createdAt,
      },
    })

    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Test fast reconcile scheduling" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    const timeoutDelays = timeoutSpy.mock.calls
      .map((call) => call[1])
      .filter((delay): delay is number => typeof delay === "number")

    expect(timeoutDelays.some((delay) => delay > 0 && delay <= 500)).toBe(true)
    expect(timeoutDelays).not.toContain(30_000)
    timeoutSpy.mockRestore()
  })

  it("hydrates pending assistant rows immediately when the selected session updatedAt advances", async () => {
    const requestedAt = new Date().toISOString()
    mockChatMessageCreate.mockResolvedValueOnce({
      data: {
        id: "msg-user-session-advanced",
        createdAt: requestedAt,
      },
    })

    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByText("Hel")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Test session update reconcile path" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    const listCallsBeforeSessionUpdate = mockChatMessageListBySession.mock.calls.length
    mockChatMessageListBySession.mockResolvedValueOnce({
      data: [
        {
          id: "msg-assistant-session-advanced",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Recovered after session update",
          createdAt: new Date(Date.parse(requestedAt) + 2_000).toISOString(),
          sequenceNumber: 3,
          metadata: JSON.stringify({
            streaming: {
              state: "complete",
            },
          }),
        },
      ],
      nextToken: null,
    })

    await act(async () => {
      subscriptions.sessionUpdate?.next({
        data: {
          onUpdateChatSession: {
            id: "sess-1",
            accountId: "acct-1",
            procedureId: "proc-1",
            category: "Console Chat",
            createdAt: "2026-03-27T00:00:00.000Z",
            updatedAt: new Date(Date.parse(requestedAt) + 2_000).toISOString(),
          },
        },
      })
    })

    await waitFor(() => {
      expect(mockChatMessageListBySession.mock.calls.length).toBeGreaterThan(listCallsBeforeSessionUpdate)
      expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
      expect(screen.getByText("Recovered after session update")).toBeInTheDocument()
    })
  })

  it("keeps thinking state when timeout reconcile finds no assistant, then recovers after terminal update", async () => {
    mockChatMessageCreate.mockResolvedValueOnce({
      data: {
        id: "msg-user-timeout-missing-assistant",
        createdAt: "2000-01-01T00:00:00.000Z",
      },
    })

    mockChatMessageListBySession
      .mockResolvedValueOnce({
        data: [],
        nextToken: null,
      })
      .mockResolvedValueOnce({
        data: [
          {
            id: "msg-assistant-timeout-delayed",
            accountId: "acct-1",
            procedureId: "proc-1",
            sessionId: "sess-1",
            role: "ASSISTANT",
            messageType: "MESSAGE",
            humanInteraction: "CHAT_ASSISTANT",
            content: "Recovered after delayed assistant row",
            createdAt: "2099-03-27T00:00:04.000Z",
            sequenceNumber: 3,
            metadata: JSON.stringify({
              streaming: {
                state: "complete",
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

    await screen.findByText("Hel")

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Test delayed assistant reconcile path" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(mockChatMessageListBySession).toHaveBeenCalledTimes(1)
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    await act(async () => {
      subscriptions.messageUpdate?.next({
        data: {
          id: "msg-user-timeout-missing-assistant",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "USER",
          messageType: "MESSAGE",
          humanInteraction: "CHAT",
          content: "Test delayed assistant reconcile path",
          createdAt: "2099-03-27T00:00:02.000Z",
          responseStatus: "COMPLETED",
          responseCompletedAt: "2099-03-27T00:00:05.000Z",
          sequenceNumber: 2,
        },
      })
    })

    await waitFor(() => {
      expect(mockChatMessageListBySession).toHaveBeenCalledTimes(2)
      expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
      expect(screen.getByText("Recovered after delayed assistant row")).toBeInTheDocument()
    })
  })

  it("reconciles pending thinking via procedure-list fallback when session list API is unavailable", async () => {
    const chatMessageModel = mockClient.models.ChatMessage as any
    const originalListBySession = chatMessageModel.listChatMessageBySessionIdAndCreatedAt
    chatMessageModel.listChatMessageBySessionIdAndCreatedAt = undefined

    try {
      mockChatMessageCreate.mockResolvedValueOnce({
        data: {
          id: "msg-user-procedure-fallback",
          createdAt: "2000-01-01T00:00:00.000Z",
        },
      })

      render(
        <ConversationViewer
          experimentId="proc-1"
          defaultSidebarCollapsed={false}
        />
      )

      await screen.findByText("Hel")

      mockChatMessageList.mockResolvedValueOnce({
        data: [
          {
            id: "msg-assistant-procedure-fallback",
            accountId: "acct-1",
            procedureId: "proc-1",
            sessionId: "sess-1",
            role: "ASSISTANT",
            messageType: "MESSAGE",
            humanInteraction: "CHAT_ASSISTANT",
            content: "Recovered via procedure fallback",
            createdAt: "2099-03-27T00:00:04.000Z",
            sequenceNumber: 3,
            metadata: JSON.stringify({
              streaming: {
                state: "complete",
              },
            }),
          },
        ],
        nextToken: null,
      })

      fireEvent.change(screen.getByPlaceholderText("Type a message"), {
        target: { value: "Test procedure fallback reconcile" },
      })
      fireEvent.click(screen.getByRole("button", { name: "Submit" }))

      await waitFor(() => {
        expect(mockChatMessageCreate).toHaveBeenCalled()
        expect(screen.getByText("Thinking")).toBeInTheDocument()
      })

      await waitFor(() => {
        expect(mockChatMessageList).toHaveBeenCalledTimes(2)
        expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
        expect(screen.getByText("Recovered via procedure fallback")).toBeInTheDocument()
      })
    } finally {
      chatMessageModel.listChatMessageBySessionIdAndCreatedAt = originalListBySession
    }
  })

  it("reconciles pending thinking via procedure-list fallback when session list call fails", async () => {
    mockChatMessageCreate.mockResolvedValueOnce({
      data: {
        id: "msg-user-procedure-fallback-error",
        createdAt: "2000-01-01T00:00:00.000Z",
      },
    })

    mockChatMessageListBySession.mockRejectedValueOnce(new Error("session list unavailable"))
    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByPlaceholderText("Type a message")
    mockChatMessageList.mockResolvedValueOnce({
      data: [
        {
          id: "msg-assistant-procedure-fallback-error",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "Recovered via procedure fallback after session list error",
          createdAt: "2099-03-27T00:00:04.000Z",
          sequenceNumber: 3,
          metadata: JSON.stringify({
            streaming: {
              state: "complete",
            },
          }),
        },
      ],
      nextToken: null,
    })
    const sessionListCallsBeforeSubmit = mockChatMessageListBySession.mock.calls.length
    const procedureListCallsBeforeSubmit = mockChatMessageList.mock.calls.length

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Test procedure fallback error path" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(mockChatMessageListBySession.mock.calls.length).toBeGreaterThan(sessionListCallsBeforeSubmit)
      expect(mockChatMessageList.mock.calls.length).toBeGreaterThan(procedureListCallsBeforeSubmit)
      expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
      expect(screen.getByText("Recovered via procedure fallback after session list error")).toBeInTheDocument()
    })
  })

  it("clears pending thinking when reconciliation list calls fail", async () => {
    mockChatMessageCreate.mockResolvedValueOnce({
      data: {
        id: "msg-user-reconcile-failure",
        createdAt: "2000-01-01T00:00:00.000Z",
      },
    })

    mockChatMessageListBySession.mockRejectedValueOnce(new Error("session list unavailable"))
    mockChatMessageList.mockRejectedValueOnce(new Error("procedure list unavailable"))

    render(
      <ConversationViewer
        experimentId="proc-1"
        defaultSidebarCollapsed={false}
      />
    )

    await screen.findByPlaceholderText("Type a message")
    const sessionListCallsBeforeSubmit = mockChatMessageListBySession.mock.calls.length
    const procedureListCallsBeforeSubmit = mockChatMessageList.mock.calls.length

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Test reconcile failure clear path" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      expect(mockChatMessageCreate).toHaveBeenCalled()
      expect(screen.getByText("Thinking")).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(mockChatMessageListBySession.mock.calls.length).toBeGreaterThan(sessionListCallsBeforeSubmit)
      expect(mockChatMessageList.mock.calls.length).toBeGreaterThan(procedureListCallsBeforeSubmit)
      expect(screen.queryByText("Thinking")).not.toBeInTheDocument()
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

  it("jumps to latest message when opening a deep-linked session", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-older",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "USER",
          messageType: "MESSAGE",
          humanInteraction: "CHAT",
          content: "older",
          createdAt: "2026-03-27T00:00:01.000Z",
          sequenceNumber: 1,
        },
        {
          id: "msg-latest",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "MESSAGE",
          humanInteraction: "CHAT_ASSISTANT",
          content: "latest",
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
        selectedSessionId="sess-1"
      />
    )

    await screen.findByText("latest")
    await waitFor(() => {
      expect(mockScrollToIndex).toHaveBeenCalledWith(
        expect.objectContaining({ index: "LAST", align: "end", behavior: "auto" })
      )
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
    expect(screen.getByTestId("console-score-workflow-summary")).toBeInTheDocument()
    expect(screen.getByText("Evaluation available")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Open workflow evaluation" })).toHaveAttribute(
      "href",
      "/lab/evaluations/eval-1"
    )
    expect(screen.getByText(/Review the result/)).toBeInTheDocument()
  })

  it("renders queued evaluation task workflow without calling it running", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-exec-tactus-eval-queued",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "TOOL_CALL",
          humanInteraction: "INTERNAL",
          toolName: "execute_tactus",
          toolParameters: JSON.stringify({ tactus: "return plexus.evaluation.run({ async = true })" }),
          toolResponse: JSON.stringify({
            ok: true,
            api_calls: ["plexus.evaluation.run"],
            value: {
              status: "queued",
              task_id: "task-queued-1",
              dispatch_status: "PENDING",
              evaluation_id: null,
              evaluation_record_created: false,
              score_version_id: "version-2",
              evaluation_type: "feedback",
            },
          }),
          content: "execute_tactus(...)",
          createdAt: "2026-03-27T00:00:03.500Z",
          sequenceNumber: 35,
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
      expect(screen.getByTestId("console-score-workflow-summary")).toBeInTheDocument()
    })
    expect(screen.getByText("Evaluation queued")).toBeInTheDocument()
    expect(screen.getByText("Task queued; evaluation record not created yet.")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Open workflow evaluation task" })).toHaveAttribute(
      "href",
      "/lab/tasks/task-queued-1"
    )
    expect(screen.queryByText("Running")).not.toBeInTheDocument()
  })

  it("renders execute_tactus evaluation output when value includes evaluationId without api_calls", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-exec-tactus-eval-id-only",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "TOOL_CALL",
          humanInteraction: "INTERNAL",
          toolName: "execute_tactus",
          toolParameters: JSON.stringify({ tactus: "return plexus.evaluation.info({ evaluation_id = 'eval-2' })" }),
          toolResponse: JSON.stringify({
            ok: true,
            value: { evaluationId: "eval-2" },
          }),
          content: "execute_tactus(...)",
          createdAt: "2026-03-27T00:00:04.000Z",
          sequenceNumber: 4,
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
      expect(screen.getByTestId("evaluation-tool-output").textContent).toContain("eval-2")
    })
  })

  it("keeps execute_tactus non-evaluation envelopes on generic ToolOutput", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-exec-tactus-non-eval",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "TOOL_CALL",
          humanInteraction: "INTERNAL",
          toolName: "execute_tactus",
          toolParameters: JSON.stringify({ tactus: "return plexus.scorecards.list({})" }),
          toolResponse: JSON.stringify({
            ok: true,
            api_calls: ["plexus.scorecards.list"],
            value: [{ id: "scorecard-1", name: "QA Scorecard" }],
          }),
          content: "execute_tactus(...)",
          createdAt: "2026-03-27T00:00:05.000Z",
          sequenceNumber: 5,
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
      expect(screen.getByText("execute_tactus output-available")).toBeInTheDocument()
    })
    expect(screen.queryByTestId("evaluation-tool-output")).not.toBeInTheDocument()
    expect(screen.getByText(/scorecard-1/)).toBeInTheDocument()
  })

  it("keeps malformed execute_tactus envelopes on generic ToolOutput", async () => {
    mockChatMessageList.mockResolvedValue({
      data: [
        {
          id: "msg-exec-tactus-malformed",
          accountId: "acct-1",
          procedureId: "proc-1",
          sessionId: "sess-1",
          role: "ASSISTANT",
          messageType: "TOOL_CALL",
          humanInteraction: "INTERNAL",
          toolName: "execute_tactus",
          toolParameters: JSON.stringify({ tactus: "return plexus.api.list({})" }),
          toolResponse: "{not-json",
          content: "execute_tactus(...)",
          createdAt: "2026-03-27T00:00:06.000Z",
          sequenceNumber: 6,
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
      expect(screen.getByText("execute_tactus input-available")).toBeInTheDocument()
    })
    expect(screen.queryByTestId("evaluation-tool-output")).not.toBeInTheDocument()
    expect(screen.getByText(/return plexus\.api\.list/)).toBeInTheDocument()
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

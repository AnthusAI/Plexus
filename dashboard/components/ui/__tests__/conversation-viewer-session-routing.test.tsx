import * as React from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import ConversationViewer, { type ChatMessage, type ChatSession } from "../conversation-viewer"
import { getClient } from "@/utils/data-operations"

jest.mock("@/utils/data-operations", () => ({
  getClient: jest.fn(),
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
    disabled,
  }: {
    children: React.ReactNode
    disabled?: boolean
  }) => <div data-disabled={disabled}>{children}</div>,
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
  Tool: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ToolHeader: ({ toolName, state }: { toolName?: string; state: string }) => (
    <div>{`${toolName || "tool"} ${state}`}</div>
  ),
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

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuItem: ({
    children,
    onSelect,
  }: {
    children: React.ReactNode
    onSelect?: (event: { preventDefault: () => void }) => void
  }) => (
    <button
      type="button"
      onClick={() => onSelect?.({ preventDefault: () => undefined })}
    >
      {children}
    </button>
  ),
}))

jest.mock("@/components/ui/timestamp", () => ({
  Timestamp: ({
    time,
    variant,
    className,
  }: {
    time: string | Date
    variant: string
    className?: string
  }) => (
    <span data-testid="timestamp" data-variant={variant} className={className}>
      {typeof time === "string" ? time : time.toISOString()}
    </span>
  ),
}))

if (typeof window !== "undefined" && !("ResizeObserver" in window)) {
  ;(window as any).ResizeObserver = class {
    observe() {}
    disconnect() {}
    unobserve() {}
  }
}

describe("ConversationViewer session-routing states", () => {
  const mockedGetClient = getClient as jest.MockedFunction<typeof getClient>

  beforeEach(() => {
    mockedGetClient.mockReset()
  })

  const sessions: ChatSession[] = [
    {
      id: "session-1",
      accountId: "acct-1",
      procedureId: "builtin:console/chat",
      name: "Console Chat",
      category: "Console Chat",
      createdAt: "2026-03-27T00:00:00.000Z",
      updatedAt: "2026-03-27T00:00:00.000Z",
      messageCount: 1,
    },
  ]

  const messages: ChatMessage[] = [
    {
      id: "msg-1",
      sessionId: "session-1",
      accountId: "acct-1",
      procedureId: "builtin:console/chat",
      role: "USER",
      messageType: "MESSAGE",
      humanInteraction: "CHAT",
      content: "hello",
      createdAt: "2026-03-27T00:00:00.000Z",
    },
  ]

  it("shows explicit not-found state and disables prompt when selected session URL is invalid", () => {
    const onSessionSelect = jest.fn()

    render(
      <ConversationViewer
        sessions={sessions}
        messages={messages}
        selectedSessionId="missing-session-id"
        onSessionSelect={onSessionSelect}
        defaultSidebarCollapsed={false}
      />
    )

    expect(screen.getByText("Session not found")).toBeInTheDocument()
    expect(
      screen.getByText(/unavailable for the current account/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/select an available session or create a new one/i)
    ).toBeInTheDocument()
    expect(screen.getByPlaceholderText("Select a session to compose a message")).toBeDisabled()

    fireEvent.click(screen.getByText("Console Chat"))
    expect(onSessionSelect).toHaveBeenCalledWith("session-1")
  })

  it("creates a new session from not-found state and routes to it", async () => {
    const onSessionSelect = jest.fn()
    const createMock = jest.fn().mockResolvedValue({
      data: {
        id: "session-new",
        accountId: "acct-1",
        procedureId: "builtin:console/chat",
        category: "Console Chat",
        createdAt: "2026-03-27T00:01:00.000Z",
        updatedAt: "2026-03-27T00:01:00.000Z",
      },
    })

    mockedGetClient.mockReturnValue({
      models: {
        ChatSession: {
          create: createMock,
        },
      },
    } as any)

    render(
      <ConversationViewer
        sessions={sessions}
        messages={messages}
        selectedSessionId="missing-session-id"
        onSessionSelect={onSessionSelect}
        defaultSidebarCollapsed={false}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "Create New Session" }))

    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith(
        expect.objectContaining({
          accountId: "acct-1",
          procedureId: "builtin:console/chat",
          category: "Optimize",
        })
      )
      expect(onSessionSelect).toHaveBeenCalledWith("session-new")
    })
  })

  it("does not render cross-session messages when no session is selected", () => {
    render(
      <ConversationViewer
        sessions={sessions}
        messages={[
          ...messages,
          {
            id: "msg-assistant-2",
            sessionId: "session-1",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            role: "ASSISTANT",
            messageType: "MESSAGE",
            humanInteraction: "CHAT_ASSISTANT",
            content: "assistant reply",
            createdAt: "2026-03-27T00:00:01.000Z",
          },
        ]}
        selectedSessionId={undefined}
        defaultSidebarCollapsed={false}
      />
    )

    expect(screen.getByText("No session selected")).toBeInTheDocument()
    expect(screen.queryByText("hello")).not.toBeInTheDocument()
    expect(screen.queryByText("assistant reply")).not.toBeInTheDocument()
  })

  it("uses matching fixed header heights for sidebar and main session header", () => {
    render(
      <ConversationViewer
        sessions={sessions}
        messages={messages}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    const sidebarHeader = screen.getByTestId("conversation-sidebar-header")
    const mainHeader = screen.getByTestId("conversation-main-header")

    expect(sidebarHeader.className).toContain("h-12")
    expect(mainHeader.className).toContain("h-12")
  })

  it("does not use category as visible session title fallback", () => {
    render(
      <ConversationViewer
        sessions={[
          {
            id: "sess-optimize-1234",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            category: "Optimize",
            createdAt: "2026-03-27T00:00:00.000Z",
            updatedAt: "2026-03-27T00:00:00.000Z",
            messageCount: 0,
          },
        ]}
        messages={[
          {
            id: "msg-unnamed-1",
            sessionId: "sess-optimize-1234",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            role: "USER",
            messageType: "MESSAGE",
            humanInteraction: "CHAT",
            content: "hello",
            createdAt: "2026-03-27T00:05:00.000Z",
          },
          {
            id: "msg-unnamed-2",
            sessionId: "sess-optimize-1234",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            role: "ASSISTANT",
            messageType: "MESSAGE",
            humanInteraction: "CHAT_ASSISTANT",
            content: "reply",
            createdAt: "2026-03-27T00:08:00.000Z",
          },
        ]}
        selectedSessionId="sess-optimize-1234"
        defaultSidebarCollapsed={false}
      />
    )

    expect(screen.queryByText("Optimize")).not.toBeInTheDocument()
    expect(screen.queryByText("Session sess-opt")).not.toBeInTheDocument()
    expect(screen.getAllByTestId("timestamp")).toHaveLength(2)
    expect(screen.getAllByText("2026-03-27T00:08:00.000Z")).toHaveLength(2)
  })

  it("hides unnamed sessions that are marked hidden-until-named", () => {
    render(
      <ConversationViewer
        sessions={[
          {
            id: "hidden-sess-1",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            category: "Optimize",
            metadata: {
              console: {
                hidden_until_named: true,
              },
            },
            createdAt: "2026-03-27T00:00:00.000Z",
            updatedAt: "2026-03-27T00:00:00.000Z",
            messageCount: 0,
          },
        ]}
        messages={[]}
        selectedSessionId="hidden-sess-1"
        defaultSidebarCollapsed={false}
      />
    )

    expect(screen.getByText("Chat Sessions (0)")).toBeInTheDocument()
    const sidebar = screen.getByTestId("conversation-sidebar-header").parentElement as HTMLElement
    expect(within(sidebar).queryByText("Session hidden-s")).not.toBeInTheDocument()
    expect(screen.getByTestId("conversation-main-header")).toHaveTextContent("New Chat")
  })

  it("keeps unnamed sessions visible when hidden flag is absent", () => {
    render(
      <ConversationViewer
        sessions={[
          {
            id: "legacy-unnamed-1",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            category: "Optimize",
            createdAt: "2026-03-27T00:00:00.000Z",
            updatedAt: "2026-03-27T00:00:00.000Z",
            messageCount: 0,
          },
        ]}
        messages={[
          {
            id: "msg-legacy-unnamed",
            sessionId: "legacy-unnamed-1",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            role: "USER",
            messageType: "MESSAGE",
            humanInteraction: "CHAT",
            content: "hello",
            createdAt: "2026-03-27T00:09:00.000Z",
          },
        ]}
        selectedSessionId="legacy-unnamed-1"
        defaultSidebarCollapsed={false}
      />
    )

    expect(screen.getByText("Chat Sessions (1)")).toBeInTheDocument()
    expect(screen.queryByText("Session legacy-u")).not.toBeInTheDocument()
    expect(screen.getAllByText("2026-03-27T00:09:00.000Z")).toHaveLength(2)
  })

  it("renames a session from the action menu and marks title source manual", async () => {
    const updateMock = jest.fn().mockResolvedValue({
      data: {
        id: "session-1",
        name: "My Renamed Session",
      },
    })

    mockedGetClient.mockReturnValue({
      models: {
        ChatSession: {
          update: updateMock,
        },
      },
    } as any)

    render(
      <ConversationViewer
        sessions={sessions}
        messages={messages}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "More options" }))
    fireEvent.click(await screen.findByText("Rename session"))

    const input = await screen.findByPlaceholderText("Session title")
    fireEvent.change(input, { target: { value: "My Renamed Session" } })
    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() => {
      const updateArg = updateMock.mock.calls[0]?.[0] || {}
      const metadataArg = updateArg.metadata
      const parsedMetadata = typeof metadataArg === "string" ? JSON.parse(metadataArg) : metadataArg
      expect(updateMock).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "session-1",
          name: "My Renamed Session",
        })
      )
      expect(parsedMetadata).toEqual(
        expect.objectContaining({
          title_source: "manual",
          console: expect.objectContaining({
            hidden_until_named: false,
          }),
        })
      )
    })

    expect(screen.getAllByText("My Renamed Session")).not.toHaveLength(0)
  })
})

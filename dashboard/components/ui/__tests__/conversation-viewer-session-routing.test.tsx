import * as React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import ConversationViewer, { type ChatMessage, type ChatSession } from "../conversation-viewer"
import { getClient } from "@/utils/data-operations"

jest.mock("@/utils/data-operations", () => ({
  getClient: jest.fn(),
}))

jest.mock("@/components/ai-elements/conversation", () => ({
  Conversation: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ConversationContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
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
            category: "Console Chat",
          }),
          expect.objectContaining({ authMode: "apiKey" })
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
})

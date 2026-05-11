import * as React from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import ConversationViewer, { type ChatMessage, type ChatSession } from "../conversation-viewer"
import { getClient } from "@/utils/data-operations"
import { getCurrentUserAttribution } from "@/utils/user-profile"

jest.mock("react-virtuoso", () => {
  const React = require("react")
  const Virtuoso = React.forwardRef(function MockVirtuoso(props: any, ref: any) {
    const { data = [], itemContent, components, className, atBottomStateChange } = props
    const Footer = components?.Footer

    React.useImperativeHandle(ref, () => ({
      scrollToIndex: jest.fn(),
    }))

    React.useEffect(() => {
      atBottomStateChange?.(true)
    }, [atBottomStateChange, data.length])

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

jest.mock("@/utils/data-operations", () => ({
  getClient: jest.fn(),
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
  DropdownMenuSeparator: () => <hr />,
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

jest.mock("@/components/ui/switch", () => ({
  Switch: ({
    checked,
    onCheckedChange,
    disabled,
    "aria-label": ariaLabel,
  }: {
    checked?: boolean
    onCheckedChange?: (checked: boolean) => void
    disabled?: boolean
    "aria-label"?: string
  }) => (
    <button
      type="button"
      role="switch"
      aria-label={ariaLabel}
      aria-checked={Boolean(checked)}
      disabled={disabled}
      onClick={() => onCheckedChange?.(!checked)}
    />
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
  const mockedGetCurrentUserAttribution = getCurrentUserAttribution as jest.MockedFunction<typeof getCurrentUserAttribution>

  beforeEach(() => {
    mockedGetClient.mockReset()
    mockedGetCurrentUserAttribution.mockResolvedValue({ createdByUserId: "user-1" })
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

  it("shows a private mode indicator in the session header", () => {
    render(
      <ConversationViewer
        sessions={[
          {
            ...sessions[0],
            metadata: {
              console: {
                mode: "planning",
                private: true,
              },
            },
          },
        ]}
        messages={messages}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    const header = screen.getByTestId("conversation-main-header")
    expect(within(header).getByText("Private")).toBeInTheDocument()
  })

  it("snapshots planning and private mode into submitted Console messages", async () => {
    const updateMock = jest.fn().mockResolvedValue({ data: { id: "session-1" } })
    const createMessageMock = jest.fn().mockResolvedValue({
      data: {
        id: "msg-new",
        createdAt: "2026-03-27T00:10:00.000Z",
      },
    })

    mockedGetClient.mockReturnValue({
      models: {
        ChatSession: {
          update: updateMock,
        },
        ChatMessage: {
          create: createMessageMock,
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

    fireEvent.click(screen.getByRole("switch", { name: "Private" }))

    await waitFor(() => {
      const metadataArg = updateMock.mock.calls[0]?.[0]?.metadata
      const parsedMetadata = typeof metadataArg === "string" ? JSON.parse(metadataArg) : metadataArg
      expect(parsedMetadata.console).toEqual(
        expect.objectContaining({
          mode: "planning",
          private: true,
          private_owner_user_id: "user-1",
          private_only: false,
          current_privacy_span_id: expect.any(String),
        })
      )
    })

    fireEvent.change(screen.getByPlaceholderText("Type a message"), {
      target: { value: "Plan this safely" },
    })
    fireEvent.click(screen.getByRole("button", { name: "Submit" }))

    await waitFor(() => {
      const metadataArg = createMessageMock.mock.calls[0]?.[0]?.metadata
      const parsedMetadata = typeof metadataArg === "string" ? JSON.parse(metadataArg) : metadataArg
      expect(parsedMetadata.console).toEqual(
        expect.objectContaining({
          mode: "planning",
          private: true,
          privacy_owner_user_id: "user-1",
          privacy_span_id: expect.any(String),
        })
      )
      expect(parsedMetadata.instrumentation.client_user_message_text).toBeUndefined()
      expect(JSON.stringify(parsedMetadata.instrumentation.client_history_snapshot)).not.toContain("Plan this safely")
    })
  })

  it("turning Plan mode off clears Private mode", async () => {
    const updateMock = jest.fn().mockResolvedValue({ data: { id: "session-1" } })

    mockedGetClient.mockReturnValue({
      models: {
        ChatSession: {
          update: updateMock,
        },
      },
    } as any)

    render(
      <ConversationViewer
        sessions={[
          {
            ...sessions[0],
            metadata: {
              console: {
                mode: "planning",
                private: true,
              },
            },
          },
        ]}
        messages={messages}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    fireEvent.click(screen.getByRole("switch", { name: "Plan mode" }))

    await waitFor(() => {
      const lastCall = updateMock.mock.calls.at(-1)?.[0] || {}
      const parsedMetadata = typeof lastCall.metadata === "string"
        ? JSON.parse(lastCall.metadata)
        : lastCall.metadata
      expect(parsedMetadata.console).toEqual(
        expect.objectContaining({
          mode: "execution",
          private: false,
        })
      )
    })
  })

  it("hides private-only sessions from non-owners", async () => {
    mockedGetCurrentUserAttribution.mockResolvedValue({ createdByUserId: "user-1" })

    render(
      <ConversationViewer
        sessions={[
          {
            ...sessions[0],
            metadata: {
              console: {
                private_only: true,
                private_owner_user_id: "user-2",
              },
            },
          },
        ]}
        messages={[]}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    await waitFor(() => {
      expect(screen.getByText("Chat Sessions (0)")).toBeInTheDocument()
    })
    const sidebar = screen.getByTestId("conversation-sidebar-header").parentElement as HTMLElement
    expect(within(sidebar).queryByText("Console Chat")).not.toBeInTheDocument()
  })

  it("collapses private message spans and tool rows for non-owners", async () => {
    mockedGetCurrentUserAttribution.mockResolvedValue({ createdByUserId: "user-1" })
    const privateConsoleMetadata = {
      console: {
        private: true,
        privacy_owner_user_id: "user-2",
        privacy_span_id: "span-1",
      },
    }

    render(
      <ConversationViewer
        sessions={sessions}
        messages={[
          ...messages,
          {
            id: "msg-private-user",
            sessionId: "session-1",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            role: "USER",
            messageType: "MESSAGE",
            humanInteraction: "CHAT",
            content: "private user text",
            metadata: privateConsoleMetadata,
            createdAt: "2026-03-27T00:00:01.000Z",
          },
          {
            id: "msg-private-tool",
            sessionId: "session-1",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            role: "ASSISTANT",
            messageType: "TOOL_CALL",
            humanInteraction: "INTERNAL",
            content: "secret tool call",
            toolName: "execute_tactus",
            toolParameters: JSON.stringify({ secret: "tool parameter" }),
            metadata: privateConsoleMetadata,
            createdAt: "2026-03-27T00:00:02.000Z",
          },
          {
            id: "msg-private-assistant",
            sessionId: "session-1",
            accountId: "acct-1",
            procedureId: "builtin:console/chat",
            role: "ASSISTANT",
            messageType: "MESSAGE",
            humanInteraction: "CHAT_ASSISTANT",
            content: "private assistant text",
            metadata: privateConsoleMetadata,
            createdAt: "2026-03-27T00:00:03.000Z",
          },
        ]}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    await waitFor(() => {
      expect(screen.getByTestId("private-conversation-span")).toBeInTheDocument()
    })
    expect(screen.getByText("hello")).toBeInTheDocument()
    expect(screen.getByText("Private conversation")).toBeInTheDocument()
    expect(screen.queryByText("private user text")).not.toBeInTheDocument()
    expect(screen.queryByText("private assistant text")).not.toBeInTheDocument()
    expect(screen.queryByText(/execute_tactus/)).not.toBeInTheDocument()
    expect(screen.queryByText(/tool parameter/)).not.toBeInTheDocument()
    expect(screen.getAllByTestId("private-conversation-span")).toHaveLength(1)
  })

  it("renders private messages normally for the owner", async () => {
    mockedGetCurrentUserAttribution.mockResolvedValue({ createdByUserId: "user-1" })

    render(
      <ConversationViewer
        sessions={sessions}
        messages={[
          {
            ...messages[0],
            content: "private owner text",
            metadata: {
              console: {
                private: true,
                privacy_owner_user_id: "user-1",
                privacy_span_id: "span-1",
              },
            },
          },
        ]}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    expect(await screen.findByText("private owner text")).toBeInTheDocument()
    expect(screen.queryByTestId("private-conversation-span")).not.toBeInTheDocument()
  })

  it("shows the attributed user avatar with the user email on user messages", async () => {
    const userGetMock = jest.fn().mockResolvedValue({
      data: {
        id: "user-1",
        email: "author@example.com",
        displayName: "Author Person",
      },
    })

    mockedGetClient.mockReturnValue({
      models: {
        User: {
          get: userGetMock,
        },
      },
    } as any)

    render(
      <ConversationViewer
        sessions={sessions}
        messages={[
          {
            ...messages[0],
            createdByUserId: "user-1",
          },
        ]}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    expect(await screen.findByLabelText("Message author: author@example.com")).toBeInTheDocument()
    expect(userGetMock).toHaveBeenCalledWith(
      { id: "user-1" },
      { authMode: "userPool" },
    )
  })

  it("shows bot avatar for bot-attributed USER chat messages", async () => {
    mockedGetClient.mockReturnValue({
      models: {
        User: {
          get: jest.fn(),
        },
      },
    } as any)

    render(
      <ConversationViewer
        sessions={sessions}
        messages={[
          {
            ...messages[0],
            metadata: {
              attribution: {
                actorType: "bot",
                actorKey: "optimizer-agent",
                displayName: "Optimizer Agent",
                avatarKey: "optimizer",
              },
            },
          },
        ]}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    expect(await screen.findByLabelText("Message author: Optimizer Agent")).toBeInTheDocument()
  })

  it("prefers createdByUserId over conflicting bot attribution metadata", async () => {
    const userGetMock = jest.fn().mockResolvedValue({
      data: {
        id: "user-1",
        email: "author@example.com",
        displayName: "Author Person",
      },
    })
    mockedGetClient.mockReturnValue({
      models: {
        User: {
          get: userGetMock,
        },
      },
    } as any)

    render(
      <ConversationViewer
        sessions={sessions}
        messages={[
          {
            ...messages[0],
            createdByUserId: "user-1",
            metadata: {
              attribution: {
                actorType: "bot",
                actorKey: "optimizer-agent",
                displayName: "Optimizer Agent",
                avatarKey: "optimizer",
              },
            },
          },
        ]}
        selectedSessionId="session-1"
        defaultSidebarCollapsed={false}
      />
    )

    expect(await screen.findByLabelText("Message author: author@example.com")).toBeInTheDocument()
    expect(screen.queryByLabelText("Message author: Optimizer Agent")).not.toBeInTheDocument()
  })
})

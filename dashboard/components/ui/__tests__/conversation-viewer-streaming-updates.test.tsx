import * as React from "react"
import { act, render, screen, waitFor } from "@testing-library/react"

import ConversationViewer from "../conversation-viewer"

const mockChatSessionList = jest.fn()
const mockChatMessageList = jest.fn()
const mockChatSessionOnCreate = jest.fn()
const mockChatMessageOnCreate = jest.fn()
const mockChatMessageOnUpdate = jest.fn()

const mockClient = {
  models: {
    ChatSession: {
      listChatSessionByProcedureIdAndCreatedAt: mockChatSessionList,
      onCreate: mockChatSessionOnCreate,
    },
    ChatMessage: {
      listChatMessageByProcedureIdAndCreatedAt: mockChatMessageList,
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
  PromptInput: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PromptInputBody: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PromptInputFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PromptInputSubmit: ({ disabled }: { disabled?: boolean }) => (
    <button disabled={disabled} aria-label="Submit">
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
    mockChatSessionOnCreate.mockReset()
    mockChatMessageOnCreate.mockReset()
    mockChatMessageOnUpdate.mockReset()

    mockChatSessionList.mockResolvedValue({
      data: [
        {
          id: "sess-1",
          accountId: "acct-1",
          procedureId: "proc-1",
          category: "Console Chat",
          status: "ACTIVE",
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
})

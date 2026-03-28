import * as React from "react"
import { fireEvent, render, screen } from "@testing-library/react"

import ConversationViewer, { type ChatMessage, type ChatSession } from "../conversation-viewer"

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

if (typeof window !== "undefined" && !("ResizeObserver" in window)) {
  ;(window as any).ResizeObserver = class {
    observe() {}
    disconnect() {}
    unobserve() {}
  }
}

describe("ConversationViewer session-routing states", () => {
  const sessions: ChatSession[] = [
    {
      id: "session-1",
      accountId: "acct-1",
      procedureId: "builtin:console/chat",
      category: "Console Chat",
      status: "ACTIVE",
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
})

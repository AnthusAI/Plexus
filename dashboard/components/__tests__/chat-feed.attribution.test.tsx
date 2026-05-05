import React from "react"
import { render, screen } from "@testing-library/react"

import { ChatFeedView, type ChatMessage } from "@/components/chat-feed"
import { getClient } from "@/utils/data-operations"

jest.mock("@/utils/data-operations", () => ({
  getClient: jest.fn(),
}))

jest.mock("@/utils/user-profile", () => ({
  getCurrentUserAttribution: jest.fn().mockResolvedValue({ createdByUserId: "user-1" }),
  gravatarAvatarUrl: jest.fn(async (email: string, size = 64) => (
    `https://www.gravatar.com/avatar/test?s=${size}&email=${encodeURIComponent(email)}`
  )),
}))

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

jest.mock("@/components/ui/scroll-area", () => ({
  ScrollArea: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

jest.mock("@/components/ui/spinner", () => ({
  Spinner: () => <span>spinner</span>,
}))

jest.mock("@/components/ui/timestamp", () => ({
  Timestamp: ({ time }: { time: string }) => <span>{time}</span>,
}))

jest.mock("@/components/ui/interactive-message", () => ({
  InteractiveMessage: () => <div>interactive</div>,
}))

jest.mock("@/components/ui/rich-message-content", () => ({
  RichMessageContent: ({ content }: { content?: string }) => <div>{content || ""}</div>,
}))

jest.mock("@/components/ui/message-utils", () => ({
  getMessageIcon: () => <span>icon</span>,
  getMessageTypeColor: () => "",
  getMessageTypeLabel: () => "message",
}))

describe("ChatFeed attribution rendering", () => {
  const mockedGetClient = getClient as jest.MockedFunction<typeof getClient>

  beforeEach(() => {
    mockedGetClient.mockReset()
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      value: jest.fn(),
      writable: true,
      configurable: true,
    })
  })

  const baseMessage: ChatMessage = {
    id: "msg-1",
    content: "hello",
    role: "USER",
    messageType: "MESSAGE",
    humanInteraction: "CHAT",
    accountId: "acct-1",
    sessionId: "session-1",
    procedureId: "proc-1",
    createdAt: "2026-05-04T00:00:00.000Z",
  }

  it("renders bot avatar for bot-attributed USER messages", async () => {
    mockedGetClient.mockReturnValue({
      models: {
        User: {
          get: jest.fn(),
        },
      },
    } as any)

    render(
      <ChatFeedView
        messages={[
          {
            ...baseMessage,
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
      />,
    )

    expect(await screen.findByTitle("Optimizer Agent")).toBeInTheDocument()
  })

  it("prefers createdByUserId over bot metadata when both are present", async () => {
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
      <ChatFeedView
        messages={[
          {
            ...baseMessage,
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
      />,
    )

    expect(await screen.findByTitle("author@example.com")).toBeInTheDocument()
    expect(screen.queryByTitle("Optimizer Agent")).not.toBeInTheDocument()
  })
})

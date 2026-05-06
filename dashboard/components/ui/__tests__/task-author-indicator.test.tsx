import React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { TaskAuthorIndicator } from "@/components/ui/task-author-indicator"

const mockUseAttributedUserProfiles = jest.fn()
const mockEnsureCurrentUserProfile = jest.fn()

jest.mock("@/components/ui/chat-message-user-avatar", () => ({
  useAttributedUserProfiles: (...args: unknown[]) => mockUseAttributedUserProfiles(...args),
}))

jest.mock("@/utils/user-profile", () => ({
  ensureCurrentUserProfile: (...args: unknown[]) => mockEnsureCurrentUserProfile(...args),
}))

describe("TaskAuthorIndicator", () => {
  beforeEach(() => {
    mockUseAttributedUserProfiles.mockReset()
    mockEnsureCurrentUserProfile.mockReset()
    mockEnsureCurrentUserProfile.mockResolvedValue(null)
  })

  it("renders avatar when createdByUserId resolves", () => {
    mockUseAttributedUserProfiles.mockReturnValue({
      "user-1": {
        id: "user-1",
        email: "owner@example.com",
        displayName: "Owner Person",
        initials: "OP",
        gravatarUrl: "https://example.com/avatar.png",
      },
    })

    render(<TaskAuthorIndicator createdByUserId="user-1" />)

    expect(screen.getByLabelText("Task author: owner@example.com")).toBeInTheDocument()
  })

  it("hides when createdByUserId is missing", () => {
    mockUseAttributedUserProfiles.mockReturnValue({})

    const { container } = render(<TaskAuthorIndicator />)
    expect(container).toBeEmptyDOMElement()
  })

  it("hides when profile is unresolved", () => {
    mockUseAttributedUserProfiles.mockReturnValue({})

    const { container } = render(<TaskAuthorIndicator createdByUserId="user-1" />)
    expect(container).toBeEmptyDOMElement()
  })

  it("falls back to current signed-in user profile when ids match", async () => {
    mockUseAttributedUserProfiles.mockReturnValue({})
    mockEnsureCurrentUserProfile.mockResolvedValue({
      id: "user-1",
      email: "owner@example.com",
      displayName: "Owner Person",
      initials: "OP",
      gravatarUrl: null,
    })

    render(<TaskAuthorIndicator createdByUserId="user-1" />)

    await waitFor(() => {
      expect(screen.getByLabelText("Task author: owner@example.com")).toBeInTheDocument()
    })
  })

  it("shows display name and email below avatar on hover", async () => {
    const user = userEvent.setup()
    mockUseAttributedUserProfiles.mockReturnValue({
      "user-1": {
        id: "user-1",
        email: "owner@example.com",
        displayName: "Owner Person",
        initials: "OP",
        gravatarUrl: "https://example.com/avatar.png",
      },
    })

    render(<TaskAuthorIndicator createdByUserId="user-1" />)

    const avatar = screen.getByLabelText("Task author: owner@example.com")
    await user.hover(avatar)

    expect(screen.getByText("Owner Person")).toBeInTheDocument()
    expect(screen.getByText("owner@example.com")).toBeInTheDocument()
  })
})

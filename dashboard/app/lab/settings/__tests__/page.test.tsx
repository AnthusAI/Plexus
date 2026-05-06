import * as React from "react"
import { render, screen } from "@testing-library/react"
import { useCurrentUserProfile } from "@/hooks/use-current-user-profile"
import LabSettings from "../page"

jest.mock("@/hooks/use-current-user-profile")

const mockUseCurrentUserProfile = useCurrentUserProfile as jest.MockedFunction<typeof useCurrentUserProfile>

describe("LabSettings", () => {
  beforeEach(() => {
    mockUseCurrentUserProfile.mockReturnValue({
      profile: {
        id: "user-1",
        email: "ada@example.com",
        displayName: "Ada Lovelace",
        initials: "AL",
        gravatarUrl: "https://www.gravatar.com/avatar/hash?s=96&d=404&r=g",
      },
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    })
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it("shows the current user email and Gravatar management button", () => {
    render(<LabSettings />)

    expect(screen.getByText("ada@example.com")).toBeInTheDocument()
    const manageLink = screen.getByRole("link", { name: /manage gravatar/i })
    expect(manageLink).toHaveAttribute("href", "https://gravatar.com/profile/avatars")
    expect(manageLink).toHaveAttribute("target", "_blank")
    expect(manageLink).toHaveAttribute("rel", "noopener noreferrer")
  })

  it("shows user id and copy affordance", () => {
    render(<LabSettings />)

    expect(screen.getByText("user-1")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /copy user id/i })).toBeEnabled()
    expect(screen.getByText(/PLEXUS_ACTOR_USER_ID/i)).toBeInTheDocument()
  })
})

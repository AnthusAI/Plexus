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
    const openSpy = jest.spyOn(window, "open").mockImplementation(() => null)
    render(<LabSettings />)

    expect(screen.getByText("ada@example.com")).toBeInTheDocument()
    const manageButton = screen.getByRole("button", { name: /manage gravatar/i })
    manageButton.click()
    expect(openSpy).toHaveBeenCalledWith(
      "https://gravatar.com/profile/avatars",
      "_blank",
      "noopener,noreferrer",
    )
    openSpy.mockRestore()
  })
})

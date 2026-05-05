import { fetchAuthSession, fetchUserAttributes, getCurrentUser } from "aws-amplify/auth"
import { getCurrentUserProfile } from "@/utils/user-profile"

jest.mock("aws-amplify/auth", () => ({
  fetchAuthSession: jest.fn(),
  fetchUserAttributes: jest.fn(),
  getCurrentUser: jest.fn(),
}))

const mockFetchAuthSession = fetchAuthSession as jest.MockedFunction<typeof fetchAuthSession>
const mockFetchUserAttributes = fetchUserAttributes as jest.MockedFunction<typeof fetchUserAttributes>
const mockGetCurrentUser = getCurrentUser as jest.MockedFunction<typeof getCurrentUser>

describe("getCurrentUserProfile", () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockGetCurrentUser.mockResolvedValue({
      userId: "user-123",
      username: "ada@example.com",
      signInDetails: { loginId: "ada@example.com" },
    } as Awaited<ReturnType<typeof getCurrentUser>>)
    mockFetchUserAttributes.mockResolvedValue({
      sub: "user-123",
      email: "ada@example.com",
      name: "Ada Lovelace",
    } as Awaited<ReturnType<typeof fetchUserAttributes>>)
    mockFetchAuthSession.mockResolvedValue({} as Awaited<ReturnType<typeof fetchAuthSession>>)
  })

  it("returns profile from user attributes when available", async () => {
    const profile = await getCurrentUserProfile()

    expect(profile).not.toBeNull()
    expect(profile?.id).toBe("user-123")
    expect(profile?.email).toBe("ada@example.com")
    expect(profile?.displayName).toBe("Ada Lovelace")
    expect(profile?.initials).toBe("AL")
    expect(profile?.gravatarUrl).toContain("https://www.gravatar.com/avatar/")
  })

  it("falls back to auth session token claims when user attributes cannot be fetched", async () => {
    mockFetchUserAttributes.mockRejectedValue(new Error("missing scope"))
    mockGetCurrentUser.mockResolvedValue({
      userId: "user-123",
      username: "opaque-username",
      signInDetails: { loginId: "opaque-username" },
    } as Awaited<ReturnType<typeof getCurrentUser>>)
    mockFetchAuthSession.mockResolvedValue({
      tokens: {
        idToken: {
          payload: {
            sub: "user-123",
            email: "token-user@example.com",
            name: "Token User",
          },
        },
      },
    } as Awaited<ReturnType<typeof fetchAuthSession>>)

    const profile = await getCurrentUserProfile()

    expect(profile).not.toBeNull()
    expect(profile?.id).toBe("user-123")
    expect(profile?.email).toBe("token-user@example.com")
    expect(profile?.displayName).toBe("Token User")
  })

  it("returns null when no email can be resolved from any source", async () => {
    mockFetchUserAttributes.mockResolvedValue({
      sub: "user-123",
    } as Awaited<ReturnType<typeof fetchUserAttributes>>)
    mockGetCurrentUser.mockResolvedValue({
      userId: "user-123",
      username: "opaque-username",
      signInDetails: { loginId: "opaque-username" },
    } as Awaited<ReturnType<typeof getCurrentUser>>)
    mockFetchAuthSession.mockResolvedValue({
      tokens: {
        idToken: {
          payload: {
            sub: "user-123",
          },
        },
      },
    } as Awaited<ReturnType<typeof fetchAuthSession>>)

    const profile = await getCurrentUserProfile()

    expect(profile).toBeNull()
  })
})

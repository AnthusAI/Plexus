import { fetchAuthSession, fetchUserAttributes, getCurrentUser } from "../auth"
import { generateClient } from "../data"
import { downloadData, getUrl, uploadData } from "../storage"
import { useAuthenticator } from "../ui-react"

describe("local Amplify compatibility shims", () => {
  beforeEach(() => {
    jest.restoreAllMocks()
  })

  it("returns a fixed authenticated demo user", async () => {
    await expect(getCurrentUser()).resolves.toMatchObject({
      userId: "demo-user",
      username: "demo@plexus.local",
    })
    await expect(fetchUserAttributes()).resolves.toMatchObject({
      sub: "demo-user",
      email: "demo@plexus.local",
      name: "Demo User",
    })
    await expect(fetchAuthSession()).resolves.toMatchObject({
      userSub: "demo-user",
      tokens: {
        idToken: {
          payload: {
            email: "demo@plexus.local",
          },
        },
      },
    })
    expect(useAuthenticator()).toMatchObject({
      authStatus: "authenticated",
      user: { userId: "demo-user" },
    })
  })

  it("implements deterministic storage placeholders", async () => {
    await expect(downloadData({ path: "reports/demo.txt" }).result).resolves.toMatchObject({
      path: "reports/demo.txt",
    })
    await expect(uploadData({ path: "reports/demo.txt", data: "demo" }).result).resolves.toMatchObject({
      path: "reports/demo.txt",
    })
    await expect(getUrl({ path: "reports/demo.txt" })).resolves.toMatchObject({
      url: expect.any(URL),
      expiresAt: expect.any(Date),
    })
  })

  it("exposes Amplify-shaped model CRUD methods over local GraphQL", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          createAccount: { id: "account-1", key: "local-demo" },
          listAccounts: {
            items: [{ id: "account-1", key: "local-demo" }],
            nextToken: null,
          },
        },
      }),
    } as Response)
    ;(globalThis as any).fetch = fetchMock

    const client = generateClient() as any
    await expect(client.models.Account.create({ id: "account-1", key: "local-demo" })).resolves.toEqual({
      data: { id: "account-1", key: "local-demo" },
    })
    await expect(client.models.Account.list()).resolves.toEqual({
      data: [{ id: "account-1", key: "local-demo" }],
      nextToken: null,
    })

    const listRequest = JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string)
    expect(listRequest.query).toContain("query LocalListAccount")
    expect(listRequest.query).toContain("listAccounts {")
    expect(listRequest.query).toMatch(/\bid\b/)
    expect(listRequest.query).not.toContain("listAccounts()")
  })
})

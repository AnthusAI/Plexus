import { fetchAuthSession, fetchUserAttributes, getCurrentUser } from "../auth"
import { generateClient } from "../data"
import { downloadData, getUrl, uploadData } from "../storage"
import { useAuthenticator } from "../ui-react"
import manifest from "../../../../services/private-graphql-proxy/schema/amplify-manifest.json"

describe("local Amplify compatibility shims", () => {
  beforeEach(() => {
    jest.restoreAllMocks()
  })

  function storageResponse(text: string, status = 200) {
    return {
      ok: status >= 200 && status < 300,
      status,
      clone() {
        return storageResponse(text, status)
      },
      async text() {
        return text
      },
      async json() {
        return JSON.parse(text)
      },
      async blob() {
        return new Blob([text])
      },
    } as Response
  }

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

  it("implements local storage through the dashboard API route", async () => {
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(storageResponse("demo-body"))
      .mockResolvedValueOnce(storageResponse(JSON.stringify({ path: "reports/demo.txt" })))
    ;(globalThis as any).fetch = fetchMock

    const download = await downloadData({ path: "reports/demo.txt" }).result
    expect(download).toMatchObject({
      path: "reports/demo.txt",
    })
    await expect(download.body.text()).resolves.toBe("demo-body")

    await expect(uploadData({ path: "reports/demo.txt", data: "demo" }).result).resolves.toMatchObject({
      path: "reports/demo.txt",
    })
    await expect(getUrl({ path: "reports/demo.txt" })).resolves.toMatchObject({
      url: expect.any(URL),
      expiresAt: expect.any(Date),
    })
    expect(fetchMock.mock.calls[0][0]).toContain("/api/local-storage?path=reports%2Fdemo.txt")
    expect(fetchMock.mock.calls[1][0]).toContain("/api/local-storage?path=reports%2Fdemo.txt")
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "PUT" })
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

  it("includes manifest primary-key fields in every generated model list selection", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: {} }),
    } as Response)
    ;(globalThis as any).fetch = fetchMock

    const client = generateClient() as any
    const models = manifest.models as Record<string, { operations: { list: string }, primaryKey?: string[] }>

    for (const modelName of Object.keys(models)) {
      await client.models[modelName].list()
      const request = JSON.parse((fetchMock.mock.calls.at(-1)?.[1] as RequestInit).body as string)
      const query = request.query as string
      for (const primaryKeyField of models[modelName].primaryKey || ["id"]) {
        expect(query).toMatch(new RegExp(`\\b${primaryKeyField}\\b`))
      }
    }
  })

  it("returns no-op subscriptions synchronously from client.graphql", () => {
    const client = generateClient() as any
    const subscription = client.graphql({
      query: "subscription LocalNoop { onCreateEvaluation { id } }",
    })

    expect(typeof subscription.subscribe).toBe("function")
    expect(subscription.subscribe()).toMatchObject({
      unsubscribe: expect.any(Function),
    })
  })
})

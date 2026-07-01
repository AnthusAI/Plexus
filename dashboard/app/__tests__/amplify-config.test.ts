import { resolveAmplifyOutputs } from "../amplify-config"

describe("resolveAmplifyOutputs", () => {
  afterEach(() => {
    jest.restoreAllMocks()
  })

  it("returns local API-key outputs in local backend mode", () => {
    const outputs = resolveAmplifyOutputs({
      NEXT_PUBLIC_PLEXUS_BACKEND: "local",
      NEXT_PUBLIC_PLEXUS_API_URL: "http://localhost:18080/graphql",
      NEXT_PUBLIC_PLEXUS_API_KEY: "local-key",
      NEXT_PUBLIC_PLEXUS_API_REGION: "us-east-1",
    }, () => null)

    expect(outputs).toMatchObject({
      data: {
        url: "http://localhost:18080/graphql",
        api_key: "local-key",
        aws_region: "us-east-1",
        default_authorization_type: "API_KEY",
        authorization_types: ["API_KEY"],
      },
    })
  })

  it("ignores legacy non-local API key/url overrides and keeps amplify outputs", () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {})
    const configuredOutputs = {
      data: {
        url: "https://example.appsync-api.us-east-1.amazonaws.com/graphql",
        default_authorization_type: "AMAZON_COGNITO_USER_POOLS",
        authorization_types: ["API_KEY", "AWS_IAM"],
      },
      auth: {
        user_pool_id: "us-east-1_example",
      },
    }

    const outputs = resolveAmplifyOutputs({
      NEXT_PUBLIC_PLEXUS_API_URL: "https://legacy.example/graphql",
      NEXT_PUBLIC_PLEXUS_API_KEY: "da2-legacy",
    }, () => configuredOutputs)

    expect(outputs).toBe(configuredOutputs)
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("Ignoring legacy NEXT_PUBLIC_PLEXUS_API_URL/NEXT_PUBLIC_PLEXUS_API_KEY"),
    )
  })

  it("returns null when non-local amplify outputs are unavailable", () => {
    const outputs = resolveAmplifyOutputs({}, () => null)
    expect(outputs).toBeNull()
  })
})

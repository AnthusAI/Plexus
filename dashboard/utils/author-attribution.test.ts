import { resolveCreatedByUserId } from "@/utils/author-attribution"

describe("resolveCreatedByUserId", () => {
  it("prefers createdByUserId when present", () => {
    expect(resolveCreatedByUserId({
      createdByUserId: "user-created",
      metadata: {
        attribution: { requestUserId: "user-request" },
      },
    })).toBe("user-created")
  })

  it("falls back to metadata attribution requestUserId", () => {
    expect(resolveCreatedByUserId({
      createdByUserId: null,
      metadata: {
        attribution: { requestUserId: "user-request" },
      },
    })).toBe("user-request")
  })

  it("supports metadata passed as JSON string", () => {
    expect(resolveCreatedByUserId({
      metadata: JSON.stringify({
        attribution: { requestUserId: "user-request" },
      }),
    })).toBe("user-request")
  })

  it("uses legacy fallback only when createdBy and metadata attribution are missing", () => {
    expect(resolveCreatedByUserId({
      legacyFallbacks: [null, "legacy-user"],
    })).toBe("legacy-user")
  })

  it("returns null for malformed metadata", () => {
    expect(resolveCreatedByUserId({
      metadata: "{not-json}",
    })).toBeNull()
  })
})

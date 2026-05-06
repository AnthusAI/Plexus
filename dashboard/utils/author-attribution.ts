type JsonRecord = Record<string, unknown>

function parseJsonObject(value: unknown): JsonRecord | null {
  if (!value) return null
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return null
    try {
      const parsed = JSON.parse(trimmed)
      return parsed && typeof parsed === "object" && !Array.isArray(parsed)
        ? (parsed as JsonRecord)
        : null
    } catch {
      return null
    }
  }
  if (typeof value === "object" && !Array.isArray(value)) {
    return value as JsonRecord
  }
  return null
}

export function parseJsonObjectLoose(value: unknown): JsonRecord | null {
  return parseJsonObject(value)
}

function cleanString(value: unknown): string | null {
  if (typeof value !== "string") return null
  const trimmed = value.trim()
  return trimmed || null
}

export function resolveCreatedByUserId(input: {
  createdByUserId?: unknown
  metadata?: unknown
  legacyFallbacks?: Array<unknown>
}): string | null {
  const explicit = cleanString(input.createdByUserId)
  if (explicit) return explicit

  const metadata = parseJsonObject(input.metadata)
  const attribution = metadata?.attribution
  const attributionObject = attribution && typeof attribution === "object" && !Array.isArray(attribution)
    ? (attribution as JsonRecord)
    : null

  const requestUserId = cleanString(attributionObject?.requestUserId)
  if (requestUserId) return requestUserId

  const userId = cleanString(attributionObject?.userId)
  if (userId) return userId

  for (const candidate of input.legacyFallbacks ?? []) {
    const resolved = cleanString(candidate)
    if (resolved) return resolved
  }

  return null
}

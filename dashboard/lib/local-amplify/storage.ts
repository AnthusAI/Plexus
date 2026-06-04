type StorageOptions = {
  path?: string
  key?: string
  data?: any
  options?: Record<string, any>
}

function objectPath(input: StorageOptions): string {
  return input.path || input.key || "local-demo-object"
}

function textBody(value = "") {
  return {
    async text() {
      return value
    },
    async json() {
      return value ? JSON.parse(value) : {}
    },
    async blob() {
      return new Blob([value])
    },
  }
}

export function downloadData(input: StorageOptions) {
  return {
    result: Promise.resolve({
      body: textBody(""),
      path: objectPath(input),
      key: objectPath(input),
    }),
    cancel() {},
    pause() {},
    resume() {},
  }
}

export function uploadData(input: StorageOptions) {
  return {
    result: Promise.resolve({
      path: objectPath(input),
      key: objectPath(input),
    }),
    cancel() {},
    pause() {},
    resume() {},
  }
}

export async function getUrl(input: StorageOptions) {
  const path = objectPath(input)
  const origin = typeof window === "undefined" ? "http://localhost:3000" : window.location.origin
  return {
    url: new URL(`/local-storage/${encodeURIComponent(path)}`, origin),
    expiresAt: new Date(Date.now() + 60 * 60 * 1000),
  }
}

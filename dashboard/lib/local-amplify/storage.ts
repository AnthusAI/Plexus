type StorageOptions = {
  path?: string
  key?: string
  data?: any
  options?: Record<string, any>
}

function objectPath(input: StorageOptions): string {
  return input.path || input.key || "local-demo-object"
}

function localStorageUrl(path: string): string {
  const encodedPath = encodeURIComponent(path)
  if (typeof window === "undefined") {
    return `http://localhost:3000/api/local-storage?path=${encodedPath}`
  }
  return `/api/local-storage?path=${encodedPath}`
}

function responseBody(response: Response) {
  return {
    async text() {
      return response.clone().text()
    },
    async json() {
      return response.clone().json()
    },
    async blob() {
      return response.clone().blob()
    },
  }
}

function uploadBody(data: any): BodyInit {
  if (data == null) return ""
  if (typeof data === "string" || data instanceof Blob || data instanceof ArrayBuffer) return data
  if (ArrayBuffer.isView(data)) return data as BodyInit
  return JSON.stringify(data)
}

export function downloadData(input: StorageOptions) {
  const path = objectPath(input)
  return {
    result: fetch(localStorageUrl(path), { method: "GET" }).then((response) => {
      if (!response.ok) {
        throw new Error(`Local storage download failed for ${path}: ${response.status}`)
      }
      return {
        body: responseBody(response),
        path,
        key: path,
      }
    }),
    cancel() {},
    pause() {},
    resume() {},
  }
}

export function uploadData(input: StorageOptions) {
  const path = objectPath(input)
  return {
    result: fetch(localStorageUrl(path), {
      method: "PUT",
      body: uploadBody(input.data),
      headers: {
        "content-type": input.options?.contentType || "application/octet-stream",
      },
    }).then((response) => {
      if (!response.ok) {
        throw new Error(`Local storage upload failed for ${path}: ${response.status}`)
      }
      return {
        path,
        key: path,
      }
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
    url: new URL(`/api/local-storage?path=${encodeURIComponent(path)}`, origin),
    expiresAt: new Date(Date.now() + 60 * 60 * 1000),
  }
}

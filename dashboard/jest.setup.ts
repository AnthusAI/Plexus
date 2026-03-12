import '@testing-library/jest-dom'

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter() {
    return {
      push: jest.fn(),
      replace: jest.fn(),
      prefetch: jest.fn()
    }
  },
  usePathname() {
    return ''
  }
}))

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

global.ResizeObserver = MockResizeObserver;
// Mock next-themes
jest.mock('next-themes', () => ({
  ThemeProvider: function ThemeProvider({ children }: { children: React.ReactNode }) { return children },
  useTheme: () => ({ theme: 'light', setTheme: jest.fn() })
}))

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
})

// Mock ResizeObserver
class ResizeObserver {
  observe = jest.fn()
  unobserve = jest.fn()
  disconnect = jest.fn()
}

window.ResizeObserver = ResizeObserver

// Mock client.models and graphql
const mockClient = {
  models: {
    Account: {
      list: jest.fn().mockResolvedValue({
        data: [],
        nextToken: null
      })
    }
  },
  graphql: jest.fn()
} as any

// Mock generateClient
const { generateClient } = jest.requireActual("aws-amplify/api")
jest.mock("aws-amplify/api", () => ({
  generateClient: jest.fn().mockReturnValue(mockClient)
}))

// Mock aws-amplify/data
jest.mock("aws-amplify/data", () => ({
  generateClient: jest.fn().mockReturnValue(mockClient)
}))

// Initialize client
declare global {
  var client: typeof mockClient
}
global.client = mockClient

// Mock listFromModel
jest.mock("@/utils/amplify-helpers", () => ({
  listFromModel: jest.fn().mockResolvedValue({
    data: [],
    nextToken: null
  })
}))

class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | null = null
  readonly rootMargin: string = ''
  readonly thresholds: ReadonlyArray<number> = []

  constructor(private callback: IntersectionObserverCallback) {
    // Immediately call the callback with empty entries to simulate intersection
    callback([], this)
  }

  observe() { return null }
  unobserve() { return null }
  disconnect() { return null }
  takeRecords(): IntersectionObserverEntry[] { return [] }
}

global.IntersectionObserver = MockIntersectionObserver as any

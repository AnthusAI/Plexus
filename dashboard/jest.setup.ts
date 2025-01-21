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

// Mock client.models
const mockClient = {
  models: {
    Account: {
      list: jest.fn().mockResolvedValue({
        data: [],
        nextToken: null
      })
    }
  }
} as any

// Mock generateClient
const { generateClient } = jest.requireActual("aws-amplify/api")
jest.mock("aws-amplify/api", () => ({
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

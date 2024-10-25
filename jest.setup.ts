import '@testing-library/jest-dom'
import type { expect } from '@jest/globals'

declare module '@jest/globals' {
  interface Matchers<R extends void | Promise<void>> {
    toBeInTheDocument(): R
    toHaveLength(length: number): R
    toHaveClass(...classNames: string[]): R
    toHaveAttribute(attr: string, value?: string): R
  }
}

/**
 * Test utilities for React Testing Library tests
 */

/**
 * Mocks window.matchMedia for testing responsive designs
 */
export function mockMatchMedia(): void {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(), // Deprecated
      removeListener: jest.fn(), // Deprecated
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });
}

/**
 * Simulates window resize events for responsive testing
 * @param width - The window width to simulate
 * @param height - The window height to simulate
 */
export function resizeWindow(width: number, height: number): void {
  // Update window dimensions
  Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: width });
  Object.defineProperty(window, 'innerHeight', { writable: true, configurable: true, value: height });
  
  // Trigger the resize event
  window.dispatchEvent(new Event('resize'));
} 
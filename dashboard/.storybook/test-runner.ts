import type { TestRunnerConfig } from '@storybook/test-runner';

const config: TestRunnerConfig = {
  setup() {
    // Mock global functions that might be used in tests
    if (typeof global !== 'undefined') {
      // Ensure StorybookTestRunnerError is properly defined
      (global as any).StorybookTestRunnerError = class StorybookTestRunnerError extends Error {
        constructor(message: string) {
          super(message);
          this.name = 'StorybookTestRunnerError';
        }
      };

      // Mock generateClient if not already mocked
      if (!(global as any).generateClient) {
        (global as any).generateClient = () => ({
          models: {
            Account: {
              list: async () => ({
                data: [
                  {
                    id: 'mock-account-1',
                    key: 'call-criteria',
                    name: 'Mock Account',
                    settings: null,
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString(),
                  }
                ]
              })
            }
          }
        });
      }
    }
  },
  
  async preVisit(page) {
    // Ensure the page is ready before running tests
    await page.waitForLoadState('networkidle');
    
    // Inject StorybookTestRunnerError into the page context
    // Define it directly without checking to avoid temporal dead zone errors
    await page.addInitScript(() => {
      if (typeof window !== 'undefined') {
        (window as any).StorybookTestRunnerError = class StorybookTestRunnerError extends Error {
          constructor(message: string) {
            super(message);
            this.name = 'StorybookTestRunnerError';
          }
        };
      }
    });
  },
  
  async postVisit(page) {
    // Wait a bit after the story loads to ensure everything is initialized
    await page.waitForTimeout(100);
  }
};

export default config;
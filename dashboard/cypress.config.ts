import { defineConfig } from 'cypress'

export default defineConfig({
  projectId: '6nv6in',
  e2e: {
    baseUrl: 'http://127.0.0.1:4000',
    supportFile: 'cypress/support/e2e.ts',
    specPattern: 'cypress/e2e/**/*.cy.{js,jsx,ts,tsx}',
    video: true,
    screenshotOnRunFailure: true,
    experimentalStudio: false
  }
}) 
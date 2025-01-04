import '@testing-library/cypress/add-commands'

declare global {
  namespace Cypress {
    interface Chainable {
      // Add custom commands here if needed
    }
  }
}

Cypress.on("uncaught:exception", (err) => {
  // Handle specific React hydration errors
  if (
    /hydrat/i.test(err.message) ||
    /Minified React error #418/.test(err.message) ||
    /Minified React error #423/.test(err.message)
  ) {
    return false;
  }
  // We want to ensure other errors fail the test
  return true;
}); 
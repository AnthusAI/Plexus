describe('Authentication', () => {
  beforeEach(() => {
    cy.visit('http://127.0.0.1:4000', {
      onBeforeLoad(win) {
        const originalHead = win.document.head.cloneNode(true);
        cy.stub(win.document, 'head').value(originalHead);
      }
    });
  });

  it('shows login form', () => {
    cy.get('[data-amplify-authenticator]').should('exist');
    cy.get('input[name="username"]').should('be.visible');
    cy.get('input[name="password"]').should('be.visible');
  });

  it('handles successful login', () => {
    cy.get('input[name="username"]').type(Cypress.env('AUTH_USERNAME'));
    cy.get('input[name="password"]').type(Cypress.env('AUTH_PASSWORD'));
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/activity');
  });

  it('shows error on invalid credentials', () => {
    cy.get('input[name="username"]').type('invalid@example.com');
    cy.get('input[name="password"]').type('wrongpassword');
    cy.get('button[type="submit"]').click();
    cy.get('[data-amplify-authenticator]').contains('Incorrect username or password');
  });
}); 
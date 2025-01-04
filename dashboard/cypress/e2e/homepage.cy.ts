describe('Homepage', () => {
  beforeEach(() => {
    cy.visit('http://127.0.0.1:4000', {
      onBeforeLoad(win) {
        const originalHead = win.document.head.cloneNode(true);
        cy.stub(win.document, 'head').value(originalHead);
      }
    });
  });

  it('loads successfully', () => {
    cy.get('[data-amplify-authenticator]', { timeout: 10000 })
      .should('exist')
      .should('be.visible');
  });
}); 
describe('Public Evaluation Route', () => {
  beforeEach(() => {
    // Intercept API calls
    cy.intercept('GET', '/evaluations/*', (req) => {
      // Extract evaluation ID from the URL
      const id = req.url.split('/').pop()
      
      if (id === 'test-evaluation') {
        req.reply({
          statusCode: 200,
          body: {
            id: 'test-evaluation',
            type: 'test-type',
            scorecard: 'test-scorecard',
            score: 'test-score',
            createdAt: '2024-02-21T00:00:00.000Z',
            title: 'Test Evaluation',
            accuracy: 0.95,
            metrics: [
              {
                name: 'Precision',
                value: 0.95,
                priority: true
              },
              {
                name: 'Recall',
                value: 0.93,
                priority: true
              }
            ],
            processedItems: 100,
            totalItems: 100,
            progress: 100,
            inferences: 100,
            cost: 0,
            status: 'COMPLETED',
            elapsedSeconds: 60,
            estimatedRemainingSeconds: 0,
            confusionMatrix: {
              matrix: [[45, 5], [7, 43]],
              labels: ['No', 'Yes']
            },
            scoreResults: [
              {
                id: 'score-1',
                value: 'Yes',
                confidence: 0.95,
                explanation: 'High confidence prediction',
                metadata: {
                  human_label: 'Yes',
                  correct: true
                }
              }
            ]
          }
        })
      } else if (id === 'not-found') {
        req.reply({
          statusCode: 404,
          body: { message: 'Evaluation not found' }
        })
      } else {
        req.reply({
          statusCode: 500,
          body: { message: 'Internal server error' }
        })
      }
    }).as('getEvaluation')
  })

  it('loads and displays evaluation successfully', () => {
    cy.visit('/evaluations/test-evaluation')
    
    // Check loading state
    cy.get('[role="status"]').should('be.visible')
    
    // Wait for API response
    cy.wait('@getEvaluation')
    
    // Check evaluation content
    cy.contains('h1', 'Evaluation Results').should('be.visible')
    cy.contains('Test Evaluation').should('be.visible')
    cy.contains('Precision: 0.95').should('be.visible')
    cy.contains('Recall: 0.93').should('be.visible')
    
    // Check confusion matrix
    cy.get('[data-testid="confusion-matrix"]').should('be.visible')
    
    // Check footer
    cy.get('footer').should('be.visible')
  })

  it('handles not found evaluations', () => {
    cy.visit('/evaluations/not-found')
    
    // Check loading state
    cy.get('[role="status"]').should('be.visible')
    
    // Wait for API response
    cy.wait('@getEvaluation')
    
    // Check error message
    cy.contains('Failed to load evaluation').should('be.visible')
  })

  it('handles server errors', () => {
    cy.visit('/evaluations/error')
    
    // Check loading state
    cy.get('[role="status"]').should('be.visible')
    
    // Wait for API response
    cy.wait('@getEvaluation')
    
    // Check error message
    cy.contains('Failed to load evaluation').should('be.visible')
  })

  it('is responsive across different screen sizes', () => {
    cy.visit('/evaluations/test-evaluation')
    cy.wait('@getEvaluation')

    // Test mobile view
    cy.viewport('iphone-x')
    cy.get('.w-\\[calc\\(100vw-2rem\\)\\]').should('be.visible')
    cy.contains('h1', 'Evaluation Results').should('be.visible')

    // Test tablet view
    cy.viewport('ipad-2')
    cy.get('.w-\\[calc\\(100vw-2rem\\)\\]').should('be.visible')
    cy.contains('h1', 'Evaluation Results').should('be.visible')

    // Test desktop view
    cy.viewport(1920, 1080)
    cy.get('.w-\\[calc\\(100vw-2rem\\)\\]').should('be.visible')
    cy.contains('h1', 'Evaluation Results').should('be.visible')
  })
}) 
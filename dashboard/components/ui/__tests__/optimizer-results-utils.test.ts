import { hydrateProcedureRunsFeedbackEvaluations } from '../optimizer-results-utils'

const mockGraphql = jest.fn()

jest.mock('aws-amplify/api', () => ({
  generateClient: () => ({
    graphql: mockGraphql,
  }),
}))

jest.mock('aws-amplify/storage', () => ({
  downloadData: jest.fn(),
}))

jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}))

describe('optimizer-results-utils procedure feedback hydration', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('attaches original and current baseline accuracies to feedback summaries', async () => {
    mockGraphql.mockImplementation(({ variables }: { variables: { id: string } }) => ({
      data: {
        getEvaluation: {
          id: variables.id,
          status: 'COMPLETED',
          createdAt: '2026-04-25T00:00:00Z',
          updatedAt: '2026-04-25T00:00:00Z',
          parameters:
            variables.id === 'eval-feedback-1'
              ? JSON.stringify({
                  metadata: {
                    baseline_evaluation_id: 'baseline-eval-1',
                    current_baseline_evaluation_id: 'current-baseline-eval-1',
                  },
                })
              : JSON.stringify({ metadata: {} }),
          accuracy:
            variables.id === 'baseline-eval-1'
              ? 72
              : variables.id === 'current-baseline-eval-1'
                ? 81
                : 87,
          processedItems: 87,
          totalItems: 100,
          metrics: JSON.stringify({ accuracy: 87 }),
          task: null,
        },
      },
    }))

    const [hydrated] = await hydrateProcedureRunsFeedbackEvaluations([
      {
        procedureId: 'proc-1',
        indexed: true,
        manifest: {
          best: {
            best_feedback_evaluation_id: 'eval-feedback-1',
          },
        },
      } as any,
    ])

    expect(hydrated.feedbackEvaluationSummary).toMatchObject({
      id: 'eval-feedback-1',
      accuracy: 87,
      baselineEvaluationId: 'baseline-eval-1',
      currentBaselineEvaluationId: 'current-baseline-eval-1',
      baselineAccuracy: 72,
      currentBaselineAccuracy: 81,
    })
  })

  it('keeps the selected feedback summary when baseline evaluations are unavailable', async () => {
    mockGraphql.mockImplementation(({ variables }: { variables: { id: string } }) => ({
      data: {
        getEvaluation:
          variables.id === 'eval-feedback-1'
            ? {
                id: variables.id,
                status: 'COMPLETED',
                createdAt: '2026-04-25T00:00:00Z',
                updatedAt: '2026-04-25T00:00:00Z',
                parameters: JSON.stringify({
                  metadata: {
                    baseline_evaluation_id: 'missing-baseline-eval',
                    current_baseline_evaluation_id: 'missing-current-baseline-eval',
                  },
                }),
                accuracy: 87,
                processedItems: 87,
                totalItems: 100,
                metrics: JSON.stringify({ accuracy: 87 }),
                task: null,
              }
            : null,
      },
    }))

    const [hydrated] = await hydrateProcedureRunsFeedbackEvaluations([
      {
        procedureId: 'proc-1',
        indexed: true,
        manifest: {
          best: {
            best_feedback_evaluation_id: 'eval-feedback-1',
          },
        },
      } as any,
    ])

    expect(hydrated.feedbackEvaluationSummary).toMatchObject({
      id: 'eval-feedback-1',
      accuracy: 87,
      baselineEvaluationId: 'missing-baseline-eval',
      currentBaselineEvaluationId: 'missing-current-baseline-eval',
      baselineAccuracy: null,
      currentBaselineAccuracy: null,
    })
  })

  it('uses procedure manifest baseline associations when the selected evaluation has none', async () => {
    mockGraphql.mockImplementation(({ variables }: { variables: { id: string } }) => ({
      data: {
        getEvaluation: {
          id: variables.id,
          status: 'COMPLETED',
          createdAt: '2026-05-03T13:35:00Z',
          updatedAt: '2026-05-03T13:35:00Z',
          parameters: JSON.stringify({ metadata: {} }),
          accuracy: 80,
          processedItems: 40,
          totalItems: 50,
          metrics: JSON.stringify({ accuracy: 80 }),
          task: null,
        },
      },
    }))

    const [hydrated] = await hydrateProcedureRunsFeedbackEvaluations([
      {
        procedureId: 'proc-1',
        indexed: true,
        manifest: {
          baseline: {
            original_feedback_evaluation_id: 'original-baseline-eval',
            current_feedback_evaluation_id: null,
          },
        },
      } as any,
    ])

    expect(hydrated.feedbackEvaluationSummary).toMatchObject({
      id: 'original-baseline-eval',
      accuracy: 80,
      baselineEvaluationId: 'original-baseline-eval',
      currentBaselineEvaluationId: null,
      baselineAccuracy: 80,
      currentBaselineAccuracy: null,
    })
  })
})

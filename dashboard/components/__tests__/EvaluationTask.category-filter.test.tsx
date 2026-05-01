import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import EvaluationTask from '@/components/EvaluationTask'

jest.mock('@/components/EvaluationTaskScoreResults', () => ({
  EvaluationTaskScoreResults: ({ selectedItemIds }: { selectedItemIds: string[] | null }) => (
    <div data-testid="selected-item-ids">{JSON.stringify(selectedItemIds)}</div>
  ),
}))

jest.mock('@/utils/amplify-client', () => ({
  getClient: () => ({
    graphql: jest.fn(({ query }: { query: string }) => {
      if (query.includes('getProcedure')) {
        return Promise.resolve({
          data: {
            getProcedure: {
              id: 'procedure-1',
              name: 'Optimizer run',
              description: 'Procedure workflow for evaluation refinement.',
              status: 'COMPLETED',
              updatedAt: '2024-01-02T00:00:00Z',
            },
          },
        })
      }

      return Promise.resolve({
        data: {
          getScoreVersion: {
            id: 'version-1',
            createdAt: '2024-01-01T00:00:00Z',
            note: 'Evaluation candidate version',
            score: {
              championVersionId: 'version-1',
            },
          },
        },
      })
    }),
  }),
}))

const makeTask = () => {
  const rootCause = {
    misclassification_analysis: {
      category_totals: {
        information_gap: 1,
      },
      item_classifications_all: [
        {
          item_id: 'item-1',
          feedback_item_id: 'fb-1',
          primary_category: 'information_gap',
          confidence: 'medium',
          rationale_full: 'Transcript missed key phrase.',
          evidence_snippets: [
            {
              source: 'edit_comment',
              quote_or_fact: 'Could hear it in audio, but transcript dropped it.',
            },
          ],
        },
      ],
      category_summaries: {
        information_gap: {
          category_summary_text: 'Missing transcript content is causing classification uncertainty.',
          item_count: 1,
          representative_evidence: [
            {
              item_id: 'item-1',
              feedback_item_id: 'fb-1',
              source: 'edit_comment',
              quote_or_fact: 'Could hear it in audio, but transcript dropped it.',
            },
          ],
        },
      },
    },
  }

  return {
    id: 'task-1',
    type: 'Accuracy Evaluation',
    scorecard: 'Test scorecard',
    score: 'Test score',
    scorecardId: 'scorecard-1',
    scoreId: 'score-1',
    scoreVersionId: 'version-1',
    procedureId: 'procedure-1',
    time: new Date().toISOString(),
    data: {
      id: 'eval-1',
      title: 'Eval',
      status: 'COMPLETED',
      processedItems: 1,
      totalItems: 1,
      progress: 100,
      inferences: 1,
      cost: 0,
      elapsedSeconds: 1,
      estimatedRemainingSeconds: 0,
      metrics: [],
      scoreResults: [
        {
          id: 'sr-1',
          value: 'No',
          confidence: 0.9,
          explanation: 'Test',
          metadata: { human_label: 'Yes', correct: false, human_explanation: null, text: 'Text' },
          trace: null,
          itemId: 'item-1',
          itemIdentifiers: [],
          feedbackItem: null,
        },
      ],
      task: {
        status: 'COMPLETED',
        stages: {
          items: [
            { id: 's1', name: 'Setup', order: 1, status: 'COMPLETED' },
            { id: 's2', name: 'Processing', order: 2, status: 'COMPLETED', processedItems: 1, totalItems: 1 },
          ],
        },
      },
      parameters: JSON.stringify({ root_cause: rootCause }),
    },
  } as any
}

const makeTaskWithScoreResultIdOnly = () => {
  const task = makeTask()
  task.data.parameters = JSON.stringify({
    root_cause: {
      misclassification_analysis: {
        category_totals: {
          information_gap: 1,
        },
        item_classifications_all: [
          {
            score_result_id: 'sr-1',
            primary_category: 'information_gap',
            confidence: 'medium',
            rationale_full: 'Matched only by score result id.',
          },
        ],
        category_summaries: {
          information_gap: {
            category_summary_text: 'Score result id only linkage.',
            item_count: 1,
          },
        },
      },
    },
  })
  return task
}

const makeTaskWithMissingCategoryLinkage = () => {
  const task = makeTask()
  task.data.parameters = JSON.stringify({
    root_cause: {
      misclassification_analysis: {
        category_totals: {
          information_gap: 1,
        },
        item_classifications_all: [
          {
            primary_category: 'information_gap',
            confidence: 'medium',
            rationale_full: 'No linkage ids on this row.',
          },
        ],
        category_summaries: {
          information_gap: {
            category_summary_text: 'No linkage ids available.',
            item_count: 1,
          },
        },
      },
    },
  })
  return task
}

const makeTaskWithFeedbackItemLinkedCategories = () => {
  const scoreConfigurationFeedbackIds = Array.from({ length: 12 }, (_, i) => `fb-sc-${i + 1}`)
  const informationGapFeedbackIds = Array.from({ length: 3 }, (_, i) => `fb-ig-${i + 1}`)

  const scoreResults = [
    ...scoreConfigurationFeedbackIds.map((feedbackId, i) => ({
      id: `sr-sc-${i + 1}`,
      value: 'No',
      confidence: 0.8,
      explanation: `Score config result ${i + 1}`,
      metadata: {
        human_label: 'Yes',
        correct: false,
        human_explanation: null,
        text: `score config ${i + 1}`,
        feedback_item_id: feedbackId,
      },
      trace: null,
      itemId: null,
      itemIdentifiers: [],
      feedbackItem: { id: feedbackId, editCommentValue: null },
    })),
    ...informationGapFeedbackIds.map((feedbackId, i) => ({
      id: `sr-ig-${i + 1}`,
      value: 'No',
      confidence: 0.7,
      explanation: `Information gap result ${i + 1}`,
      metadata: {
        human_label: 'Yes',
        correct: false,
        human_explanation: null,
        text: `information gap ${i + 1}`,
        feedback_item_id: feedbackId,
      },
      trace: null,
      itemId: null,
      itemIdentifiers: [],
      feedbackItem: { id: feedbackId, editCommentValue: null },
    })),
  ]

  const task = makeTask()
  task.data.scoreResults = scoreResults
  task.data.totalItems = scoreResults.length
  task.data.processedItems = scoreResults.length
  task.data.parameters = JSON.stringify({
    root_cause: {
      misclassification_analysis: {
        category_totals: {
          score_configuration_problem: 12,
          information_gap: 3,
        },
        item_classifications_all: [
          ...scoreConfigurationFeedbackIds.map(feedbackId => ({
            feedback_item_id: feedbackId,
            primary_category: 'score_configuration_problem',
            confidence: 'high',
            rationale_full: `Config issue for ${feedbackId}.`,
          })),
          ...informationGapFeedbackIds.map(feedbackId => ({
            feedback_item_id: feedbackId,
            primary_category: 'information_gap',
            confidence: 'medium',
            rationale_full: `Info gap for ${feedbackId}.`,
          })),
        ],
        category_summaries: {
          score_configuration_problem: {
            category_summary_text: 'Prompt/config causes most errors.',
            item_count: 12,
          },
          information_gap: {
            category_summary_text: 'Missing context causes a smaller set of errors.',
            item_count: 3,
          },
        },
      },
    },
  })
  return task
}

describe('EvaluationTask category summary drill-down', () => {
  const readSelectedItemIds = () => JSON.parse(screen.getByTestId('selected-item-ids').textContent || 'null')

  test('applies category filter and auto-selects first matching score result', async () => {
    const onSelectScoreResult = jest.fn()
    render(<EvaluationTask variant="detail" task={makeTask()} onSelectScoreResult={onSelectScoreResult} />)

    fireEvent.click(screen.getByRole('button', { name: /View items \(1\)/i }))

    expect(screen.getByText('Filtered by category: Information gap')).toBeInTheDocument()
    expect(screen.getByTestId('selected-item-ids')).toHaveTextContent('["sr-1"]')
    expect(onSelectScoreResult).toHaveBeenCalledWith('sr-1')

    fireEvent.click(screen.getByRole('button', { name: /Clear category filter/i }))
    expect(screen.getByTestId('selected-item-ids')).toHaveTextContent('null')

    await waitFor(() => {
      expect(screen.getByText('Champion')).toBeInTheDocument()
    })
  })

  test('filters by score_result_id linkage when item_id is unavailable', async () => {
    const onSelectScoreResult = jest.fn()
    render(<EvaluationTask variant="detail" task={makeTaskWithScoreResultIdOnly()} onSelectScoreResult={onSelectScoreResult} />)

    fireEvent.click(screen.getByRole('button', { name: /View items \(1\)/i }))

    expect(screen.getByTestId('selected-item-ids')).toHaveTextContent('["sr-1"]')
    expect(onSelectScoreResult).toHaveBeenCalledWith('sr-1')
  })

  test('applies empty category filter when linkage ids are missing', async () => {
    render(<EvaluationTask variant="detail" task={makeTaskWithMissingCategoryLinkage()} />)

    fireEvent.click(screen.getByRole('button', { name: /View items \(1\)/i }))

    expect(screen.getByTestId('selected-item-ids')).toHaveTextContent('[]')
  })

  test('filters full 12-item category when linkage is primarily feedback_item_id', async () => {
    render(<EvaluationTask variant="detail" task={makeTaskWithFeedbackItemLinkedCategories()} />)

    fireEvent.click(screen.getByRole('button', { name: /View items \(12\)/i }))

    const selected = readSelectedItemIds()
    expect(Array.isArray(selected)).toBe(true)
    expect(selected).toHaveLength(12)
    expect(selected).toEqual(expect.arrayContaining(['sr-sc-1', 'sr-sc-12']))
    expect(selected).not.toEqual(expect.arrayContaining(['sr-ig-1']))
  })

  test('keeps category filters isolated between 12-item and 3-item categories', async () => {
    render(<EvaluationTask variant="detail" task={makeTaskWithFeedbackItemLinkedCategories()} />)

    fireEvent.click(screen.getByRole('button', { name: /View items \(12\)/i }))
    const firstSelection = readSelectedItemIds()

    fireEvent.click(screen.getByRole('button', { name: /View items \(3\)/i }))
    const secondSelection = readSelectedItemIds()

    expect(firstSelection).toHaveLength(12)
    expect(secondSelection).toHaveLength(3)
    expect(firstSelection).not.toEqual(secondSelection)
    expect(secondSelection).toEqual(expect.arrayContaining(['sr-ig-1', 'sr-ig-3']))
    expect(secondSelection).not.toEqual(expect.arrayContaining(['sr-sc-1']))
  })

  test('renders score version and procedure related-resource cards in detail view', async () => {
    const { container } = render(<EvaluationTask variant="detail" task={makeTask()} />)

    await waitFor(() => {
      expect(screen.getByText('Champion')).toBeInTheDocument()
    })

    expect(screen.getByText('Score Version')).toBeInTheDocument()
    expect(screen.getByText('Procedure')).toBeInTheDocument()
    expect(screen.getByText('Optimizer run')).toBeInTheDocument()
    expect(container.querySelector('a[href="/lab/scorecards/scorecard-1"]')).toBeTruthy()
    expect(container.querySelector('a[href="/lab/scorecards/scorecard-1/scores/score-1/versions/version-1"]')).toBeTruthy()
    expect(container.querySelector('a[href="/lab/procedures/procedure-1"]')).toBeTruthy()
  })

  test('omits procedure related-resource card when no procedure is associated', async () => {
    render(<EvaluationTask variant="detail" task={{ ...makeTask(), procedureId: undefined }} />)

    expect(screen.getByText('Score Version')).toBeInTheDocument()
    expect(screen.queryByText('Procedure')).not.toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Champion')).toBeInTheDocument()
    })
  })
})

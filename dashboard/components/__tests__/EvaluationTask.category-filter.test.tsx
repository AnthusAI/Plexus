import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import EvaluationTask from '@/components/EvaluationTask'

jest.mock('@/components/EvaluationTaskScoreResults', () => ({
  EvaluationTaskScoreResults: ({ selectedItemIds }: { selectedItemIds: string[] | null }) => (
    <div data-testid="selected-item-ids">{JSON.stringify(selectedItemIds)}</div>
  ),
}))

const makeTask = () => {
  const rootCause = {
    topics: [
      {
        topic_id: 1,
        label: 'Transcript omission pattern',
        member_count: 1,
        exemplars: [],
      },
    ],
    misclassification_analysis: {
      category_totals: {
        information_gap: 1,
      },
      item_classifications: [
        {
          item_id: 'item-1',
          feedback_item_id: 'fb-1',
          primary_category: 'information_gap',
          confidence: 'medium',
          rationale: 'Transcript missed key phrase.',
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
      category_hierarchy: [
        {
          category_key: 'information_gap',
          category_label: 'Information gap',
          item_count: 1,
          share: 1.0,
          summary_text: 'Missing transcript content is causing classification uncertainty.',
          top_patterns: [{ pattern: 'transcript omission', count: 1 }],
          topics: [
            {
              topic_id: 1,
              label: 'Transcript omission pattern',
              member_count: 1,
              topic_category_purity: 1.0,
              category_counts: { information_gap: 1 },
              detailed_explanation: 'Transcript dropped critical customer statement.',
              improvement_suggestion: 'Escalate transcript quality remediation.',
              score_fix_candidate_count: 0,
              examples: [
                {
                  item_id: 'item-1',
                  feedback_item_id: 'fb-1',
                  initial_answer_value: 'No',
                  final_answer_value: 'Yes',
                  detailed_cause: 'Classifier did not receive decisive phrase due to transcript gap.',
                  suggested_fix: null,
                  misclassification_classification: {
                    primary_category: 'information_gap',
                    confidence: 'medium',
                    rationale: 'Transcript missed key phrase.',
                    evidence_snippets: [
                      {
                        source: 'edit_comment',
                        quote_or_fact: 'Could hear it in audio, but transcript dropped it.',
                      },
                    ],
                  },
                },
              ],
            },
          ],
        },
      ],
    },
  }

  return {
    id: 'task-1',
    type: 'Accuracy Evaluation',
    scorecard: 'Test scorecard',
    score: 'Test score',
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

describe('EvaluationTask category summary drill-down', () => {
  test('renders unified hierarchy and applies category/topic filters to score results', () => {
    render(<EvaluationTask variant="detail" task={makeTask()} />)

    expect(screen.getByText('Category triage hierarchy')).toBeInTheDocument()
    expect(screen.queryByText('Category summaries')).not.toBeInTheDocument()
    expect(screen.queryByText('Misclassified items')).not.toBeInTheDocument()
    expect(screen.getByText('Transcript omission pattern')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Transcript omission pattern/i }))
    expect(screen.getByText(/Could hear it in audio, but transcript dropped it/i)).toBeInTheDocument()
    expect(screen.getByText(/Triage confidence: medium/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /View topic items/i }))
    expect(screen.getByText('Filtered by topic: Transcript omission pattern')).toBeInTheDocument()
    expect(screen.getByTestId('selected-item-ids')).toHaveTextContent('["item-1"]')

    fireEvent.click(screen.getByRole('button', { name: /View 1 item in score results/i }))
    expect(screen.getByText('Filtered by category: Information gap')).toBeInTheDocument()
    expect(screen.getByTestId('selected-item-ids')).toHaveTextContent('["item-1"]')

    fireEvent.click(screen.getByRole('button', { name: /Clear category filter/i }))
    expect(screen.getByTestId('selected-item-ids')).toHaveTextContent('null')
  })
})

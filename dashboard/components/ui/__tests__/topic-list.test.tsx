import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { TopicList } from '@/components/ui/topic-list'

describe('TopicList misclassification drill-down', () => {
  test('renders item-level triage details and forwards metadata through onTopicFilter', () => {
    const onTopicFilter = jest.fn()
    const topics = [
      {
        topic_id: 1,
        label: 'False positive pattern',
        memory_weight: 1,
        memory_tier: 'hot',
        member_count: 1,
        exemplars: [
          {
            text: 'Agent said free service',
            item_id: 'item-1',
            initial_answer_value: 'Yes',
            final_answer_value: 'No',
            misclassification_classification: {
              primary_category: 'score_configuration_problem',
              confidence: 'high',
              rationale: 'Prompt over-triggered on free-service language.',
              evidence_snippets: [
                {
                  source: 'score_explanation',
                  quote_or_fact: 'Flagged phrase "free service".',
                },
              ],
            },
            detailed_cause: 'The score over-indexes on free-service language.',
            suggested_fix: 'Add a safe-harbor when no payment obligation is described.',
          },
        ],
      },
    ] as any

    render(<TopicList topics={topics} onTopicFilter={onTopicFilter} />)

    fireEvent.click(screen.getByRole('button', { name: /false positive pattern/i }))

    expect(screen.getByText('Misclassified items')).toBeInTheDocument()
    expect(screen.getByText('Score configuration')).toBeInTheDocument()
    expect(screen.getByText(/Prompt over-triggered on free-service language/i)).toBeInTheDocument()

    expect(onTopicFilter).toHaveBeenCalledWith(
      ['item-1'],
      expect.objectContaining({
        'item-1': expect.objectContaining({
          misclassification_category: 'score_configuration_problem',
          misclassification_confidence: 'high',
          misclassification_rationale: 'Prompt over-triggered on free-service language.',
          detailed_cause: 'The score over-indexes on free-service language.',
          suggested_fix: 'Add a safe-harbor when no payment obligation is described.',
        }),
      })
    )
  })
})

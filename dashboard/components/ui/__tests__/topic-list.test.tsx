import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { TopicList } from '@/components/ui/topic-list'

describe('TopicList misclassification drill-down', () => {
  test('expands without filtering, then filters only via explicit action button', () => {
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
    expect(onTopicFilter).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /View items \(1\)/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /View items \(1\)/i }))
    expect(onTopicFilter).toHaveBeenCalledWith(['item-1'], 'False positive pattern')
  })

  test('hides leaked lua table pointer strings in topic label and root cause', () => {
    const topics = [
      {
        topic_id: 2,
        label: '<Lua table at 0x11a82bf10>',
        cause: 'Root cause: <Lua table at 0x380f0b510>',
        memory_weight: 1,
        memory_tier: 'warm',
        member_count: 4,
        exemplars: [{ text: 'example', item_id: 'item-2' }],
      },
    ] as any

    render(<TopicList topics={topics} />)

    expect(screen.getByText('Unlabeled topic')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /unlabeled topic/i }))
    expect(screen.queryByText(/Root cause:/i)).not.toBeInTheDocument()
  })
})

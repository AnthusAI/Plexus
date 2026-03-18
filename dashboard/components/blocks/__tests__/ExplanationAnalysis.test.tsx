import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'

import ExplanationAnalysis from '../ExplanationAnalysis'

jest.mock('vaul', () => {
  const React = require('react')
  const Primitive = React.forwardRef((props: any, ref: any) => <div ref={ref} {...props} />)
  Primitive.displayName = 'VaulPrimitive'

  return {
    Drawer: {
      Root: Primitive,
      Trigger: Primitive,
      Portal: Primitive,
      Close: Primitive,
      Overlay: Primitive,
      Content: Primitive,
      Title: Primitive,
      Description: Primitive,
    },
  }
}, { virtual: true })

jest.mock('aws-amplify/storage', () => ({
  downloadData: jest.fn(),
}))

const { downloadData } = jest.requireMock('aws-amplify/storage') as {
  downloadData: jest.Mock
}

describe('ExplanationAnalysis block', () => {
  const baseProps = {
    config: {},
    name: 'Explanation Analysis',
    position: 0,
    type: 'ExplanationAnalysis',
    id: 'rb-1',
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('exposes the ExplanationAnalysis block class identifier', () => {
    expect((ExplanationAnalysis as any).blockClass).toBe('ExplanationAnalysis')
  })

  it('renders inline explanation topics', () => {
    render(
      <ExplanationAnalysis
        {...baseProps}
        output={{
          type: 'ExplanationAnalysis',
          items_processed: 2,
          total_score_results_retrieved: 5,
          scores: [
            {
              score_id: '44245',
              score_name: 'Program Match',
              items_processed: 2,
              topics: [
                {
                  cluster_id: 0,
                  label: 'Coverage Mismatch',
                  keywords: ['coverage'],
                  exemplars: [{ text: 'Example explanation', item_id: 'item-1' }],
                  member_count: 2,
                  memory_weight: 0.5,
                  memory_tier: 'warm',
                  lifecycle_tier: 'new',
                },
              ],
            },
          ],
        }}
      />
    )

    expect(screen.getByText('Semantic topics inferred from production ScoreResult explanations.')).toBeInTheDocument()
    expect(screen.getByText('Program Match')).toBeInTheDocument()
    expect(screen.getByText('Coverage Mismatch')).toBeInTheDocument()
  })

  it('loads compacted output attachments when present', async () => {
    downloadData.mockReturnValue({
      result: Promise.resolve({
        body: {
          text: async () =>
            JSON.stringify({
              type: 'ExplanationAnalysis',
              items_processed: 3,
              scores: [
                {
                  score_id: '44245',
                  score_name: 'Program Match',
                  items_processed: 3,
                  topics: [
                    {
                      cluster_id: 1,
                      label: 'Policy Gap',
                      keywords: ['policy'],
                      exemplars: [{ text: 'Loaded from attachment' }],
                      member_count: 3,
                      memory_weight: 0.5,
                      memory_tier: 'warm',
                      lifecycle_tier: 'trending',
                    },
                  ],
                },
              ],
            }),
        },
      }),
    })

    render(
      <ExplanationAnalysis
        {...baseProps}
        output={{
          type: 'ExplanationAnalysis',
          output_compacted: true,
          output_attachment: 'reportblocks/rb-1/output-rb-1.json',
          scores: [],
        }}
      />
    )

    expect(screen.getByText('Loading attached output…')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Policy Gap')).toBeInTheDocument()
    })
  })
})

import React from 'react'
import { render, screen } from '@testing-library/react'
import { EvaluationListAccuracyBar } from '@/components/EvaluationListAccuracyBar'

describe('EvaluationListAccuracyBar', () => {
  it('renders visibly separate original and current baseline markers when accuracies overlap', () => {
    render(
      <EvaluationListAccuracyBar
        progress={100}
        accuracy={80}
        baselineAccuracy={76.78571428571429}
        currentBaselineAccuracy={76.78571428571429}
      />
    )

    const originalMarker = screen.getByLabelText('Original baseline marker')
    const currentMarker = screen.getByLabelText('Current best baseline marker')

    expect(originalMarker).toHaveStyle({ top: '0px' })
    expect(originalMarker).toHaveStyle({ height: '50%' })
    expect(originalMarker).toHaveStyle({ width: '1px' })
    expect(currentMarker).toHaveStyle({ top: '50%' })
    expect(currentMarker).toHaveStyle({ height: '50%' })
    expect(currentMarker).toHaveStyle({ width: '2px' })
  })
})

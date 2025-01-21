import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import MetricsGauges from '@/components/MetricsGauges'
import { describe, it, expect } from '@jest/globals'

describe('MetricsGauges', () => {
  const mockGauges = [
    { id: 'gauge1', value: 30, label: 'Metric 1' },
    { id: 'gauge2', value: 50, label: 'Metric 2' },
  ]

  it('renders the component', () => {
    render(<MetricsGauges gauges={mockGauges} />)
    const metricsGaugesElement = screen.getByTestId('metrics-gauges')
    expect(metricsGaugesElement).toBeInTheDocument()
  })

  it('renders the correct number of gauges', () => {
    render(<MetricsGauges gauges={mockGauges} />)
    const gaugeLabels = screen.getAllByText(/Metric \d/)
    expect(gaugeLabels).toHaveLength(2)
  })

  it('displays the correct labels', () => {
    render(<MetricsGauges gauges={mockGauges} />)
    mockGauges.forEach((gauge) => {
      expect(screen.getByText(gauge.label)).toBeInTheDocument()
    })
  })
})

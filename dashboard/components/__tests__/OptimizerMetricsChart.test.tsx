import React from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import OptimizerMetricsChart, { type IterationData } from '@/components/OptimizerMetricsChart'

jest.mock('@/components/ui/chart', () => ({
  ChartContainer: ({ children }: any) => <div data-testid="chart-container">{children}</div>,
}))

jest.mock('recharts', () => ({
  CartesianGrid: () => null,
  Line: () => null,
  LineChart: ({ children }: any) => <div>{children}</div>,
  ReferenceLine: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}))

describe('OptimizerMetricsChart dataset toggle', () => {
  const iterations: IterationData[] = [
    {
      iteration: 0,
      label: 'Baseline',
      recent_metrics: { alignment: 0.6, accuracy: 80, precision: 79, recall: 78 },
      regression_metrics: { alignment: 0.58, accuracy: 77, precision: 76, recall: 75 },
      accepted: true,
    },
    {
      iteration: 1,
      label: 'Cycle 1',
      recent_metrics: { alignment: 0.7, accuracy: 82, precision: 81, recall: 80 },
      regression_metrics: { alignment: 0.68, accuracy: 78, precision: 77, recall: 76 },
      accepted: true,
    },
  ]

  it('renders Overall/Recent/Regression labels and emits renamed mode values', async () => {
    const onDatasetViewChange = jest.fn()

    render(
      <OptimizerMetricsChart
        iterations={iterations}
        onDatasetViewChange={onDatasetViewChange}
      />
    )

    const overall = screen.getByRole('button', { name: 'Overall' })
    const recent = screen.getByRole('button', { name: 'Recent' })
    const regression = screen.getByRole('button', { name: 'Regression' })

    expect(overall).toBeInTheDocument()
    expect(recent).toBeInTheDocument()
    expect(regression).toBeInTheDocument()

    await userEvent.click(recent)
    await userEvent.click(regression)
    await userEvent.click(overall)

    expect(onDatasetViewChange).toHaveBeenNthCalledWith(1, 'recent')
    expect(onDatasetViewChange).toHaveBeenNthCalledWith(2, 'regression')
    expect(onDatasetViewChange).toHaveBeenNthCalledWith(3, 'overall')
  })
})

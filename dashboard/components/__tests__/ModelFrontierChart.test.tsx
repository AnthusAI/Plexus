import React from 'react'
import { render, screen } from '@testing-library/react'
import ModelFrontierChart, { type ModelFrontierRow } from '@/components/ModelFrontierChart'

jest.mock('@/components/ui/chart', () => ({
  ChartContainer: ({ children }: any) => <div data-testid="chart-container">{children}</div>,
}))

jest.mock('recharts', () => ({
  CartesianGrid: () => null,
  LabelList: () => null,
  ReferenceLine: () => null,
  Scatter: ({ data }: any) => <div data-testid="frontier-scatter" data-point-count={data.length} />,
  ScatterChart: ({ children }: any) => <div>{children}</div>,
  Tooltip: () => null,
  XAxis: ({ scale }: any) => <div data-testid="frontier-x-axis" data-scale={scale} />,
  YAxis: () => null,
  ZAxis: () => null,
}))

describe('ModelFrontierChart', () => {
  const rows: ModelFrontierRow[] = [
    {
      label: 'current',
      model_name: 'gpt-5-mini',
      cost_axis: 0.02,
      accuracy_axis: 0.72,
      total_cost: 2,
      processed_items: 100,
      is_current: true,
      is_pareto_frontier: true,
      status: 'completed',
    },
    {
      label: 'gpt-5.4-nano / medium',
      model_name: 'gpt-5.4-nano',
      reasoning_effort: 'medium',
      verbosity: 'medium',
      cost_axis: 0.01,
      accuracy_axis: 0.7,
      total_cost: 1,
      processed_items: 100,
      is_pareto_frontier: true,
      status: 'completed',
    },
    {
      label: 'errored',
      model_name: 'gpt-5.4-nano',
      status: 'error',
      error: 'Evaluation failed',
    },
  ]

  it('renders cost-vs-accuracy frontier points and summary counts', () => {
    render(<ModelFrontierChart rows={rows} />)

    expect(screen.getByText('Model Frontier')).toBeInTheDocument()
    expect(screen.getByText('3 variants')).toBeInTheDocument()
    expect(screen.getByText('2 frontier')).toBeInTheDocument()
    expect(screen.getByText('1 errors')).toBeInTheDocument()
    expect(screen.getByTestId('frontier-scatter')).toHaveAttribute('data-point-count', '2')
    expect(screen.getByTestId('frontier-x-axis')).toHaveAttribute('data-scale', 'log')
    expect(screen.getByText('Feedback AC1')).toBeInTheDocument()
    expect(screen.getByText('gpt-5.4-nano / medium')).toBeInTheDocument()
  })
})

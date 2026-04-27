import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ProceduresGauges } from '../ProceduresGauges'
import { BaseGauges } from '../BaseGauges'
import { useEvaluationsMetrics, useProceduresMetrics } from '@/hooks/useUnifiedMetrics'

jest.mock('../BaseGauges', () => ({
  BaseGauges: jest.fn(({ config, data }) => (
    <div data-testid="base-gauges">
      <div>{config.gauges.map((gauge: any) => gauge.title).join('|')}</div>
      <pre data-testid="base-gauges-data">{JSON.stringify(data)}</pre>
    </div>
  )),
}))

jest.mock('@/hooks/useUnifiedMetrics', () => ({
  useProceduresMetrics: jest.fn(),
  useEvaluationsMetrics: jest.fn(),
}))

const mockUseProceduresMetrics = useProceduresMetrics as jest.Mock
const mockUseEvaluationsMetrics = useEvaluationsMetrics as jest.Mock
const mockBaseGauges = BaseGauges as jest.Mock

describe('ProceduresGauges', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockUseProceduresMetrics.mockReturnValue({
      metrics: {
        itemsPerHour: 2,
        itemsAveragePerHour: 1,
        itemsPeakHourly: 10,
        itemsTotal24h: 12,
        chartData: [
          {
            time: '10:00',
            items: 2,
            bucketStart: '2026-04-27T10:00:00.000Z',
            bucketEnd: '2026-04-27T11:00:00.000Z',
          },
        ],
        lastUpdated: new Date('2026-04-27T11:00:00.000Z'),
        hasErrorsLast24h: false,
        totalErrors24h: 0,
      },
      isLoading: false,
      error: null,
    })
    mockUseEvaluationsMetrics.mockReturnValue({
      metrics: {
        itemsPerHour: 3,
        itemsAveragePerHour: 2,
        itemsPeakHourly: 10,
        itemsTotal24h: 18,
        chartData: [
          {
            time: '10:00',
            items: 3,
            bucketStart: '2026-04-27T10:00:00.000Z',
            bucketEnd: '2026-04-27T11:00:00.000Z',
          },
        ],
        lastUpdated: new Date('2026-04-27T11:00:00.000Z'),
        hasErrorsLast24h: false,
        totalErrors24h: 0,
      },
      isLoading: false,
      error: null,
    })
  })

  it('renders procedures and evaluations rate gauges from one chart payload', () => {
    render(<ProceduresGauges />)

    expect(screen.getByText('Procedures / hour|Evaluations / hour')).toBeInTheDocument()

    const call = mockBaseGauges.mock.calls[0][0]
    expect(call.config.gauges).toHaveLength(2)
    expect(call.config.chartAreas.map((area: any) => area.dataKey)).toEqual(['procedures', 'evaluations'])
    expect(call.data.proceduresPerHour).toBe(2)
    expect(call.data.evaluationsPerHour).toBe(3)
    expect(call.data.chartData).toEqual([
      expect.objectContaining({
        time: '10:00',
        procedures: 2,
        evaluations: 3,
      }),
    ])
  })
})

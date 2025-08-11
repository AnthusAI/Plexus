import { __testUtils as utils } from '../../utils/cost-analysis'

describe('cost-analysis buildQuery', () => {
  it('uses scorecard GSI with sort DESC and optional score filter', () => {
    const { query, topKey, variableNames } = (utils as any).buildQuery({ scorecardId: 'SC1', scoreId: 'S1' })
    expect(topKey).toBe('listScoreResultByScorecardIdAndUpdatedAt')
    expect(query).toMatch(/sortDirection:\s*DESC/)
    expect(query).toMatch(/filter:\s*\{\s*scoreId:\s*\{\s*eq:\s*\$scoreId\s*\}\s*\}/)
    expect(variableNames).toEqual(['scorecardId', 'scoreId'])
  })

  it('uses account GSI fallback with optional score filter', () => {
    const { query, topKey, variableNames } = (utils as any).buildQuery({ accountId: 'A1', scoreId: 'S1' })
    expect(topKey).toBe('listScoreResultByAccountIdAndUpdatedAt')
    expect(query).toMatch(/sortDirection:\s*DESC/)
    expect(query).toMatch(/filter:\s*\{\s*scoreId:\s*\{\s*eq:\s*\$scoreId\s*\}\s*\}/)
    expect(variableNames).toEqual(['accountId', 'scoreId'])
  })
})

import { fetchCostAnalysisScoreResults, __testUtils } from '../cost-analysis'
import { graphqlRequest } from '../amplify-client'

jest.mock('../amplify-client', () => ({
  graphqlRequest: jest.fn(),
  handleGraphQLErrors: jest.fn()
}))

const mockedRequest = graphqlRequest as unknown as jest.Mock

describe('cost-analysis utilities', () => {
  beforeEach(() => {
    jest.useFakeTimers()
    jest.setSystemTime(new Date('2025-01-02T12:00:00.000Z'))
    mockedRequest.mockReset()
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  test('computeWindow defaults to 24h when hours provided as null and days missing', () => {
    const { startTime, endTime } = __testUtils.computeWindow(undefined, 24)
    expect(new Date(endTime).toISOString()).toBe('2025-01-02T12:00:00.000Z')
    expect(new Date(startTime).toISOString()).toBe('2025-01-01T12:00:00.000Z')
  })

  test('when only scoreId provided (no scorecardId), defaults to account query and relies on client-side filtering', () => {
    const q = __testUtils.buildQuery({ accountId: 'A1', scoreId: 'S1' })
    expect(q.topKey).toBe('listScoreResultByAccountIdAndUpdatedAt')
    expect(q.variableNames).toEqual(['accountId'])
  })

  test('buildQuery selects scorecard-based GSI when scorecardId provided', () => {
    const q = __testUtils.buildQuery({ scorecardId: 'SC1' })
    expect(q.topKey).toBe('listScoreResultByScorecardIdAndUpdatedAt')
    expect(q.variableNames).toEqual(['scorecardId'])
  })

  test('buildQuery selects account-based GSI by default', () => {
    const q = __testUtils.buildQuery({ accountId: 'A1' })
    expect(q.topKey).toBe('listScoreResultByAccountIdAndUpdatedAt')
    expect(q.variableNames).toEqual(['accountId'])
  })

  test('filters out results with null/absent cost but keeps zero values', async () => {
    mockedRequest.mockResolvedValueOnce({
      data: {
        listScoreResultByAccountIdAndUpdatedAt: {
          items: [
            { id: '1', itemId: 'i1', accountId: 'A', createdAt: 'x', updatedAt: 'x', cost: { total_cost: 0 } }, // keep
            { id: '2', itemId: 'i2', accountId: 'A', createdAt: 'x', updatedAt: 'x', cost: null }, // drop
            { id: '3', itemId: 'i3', accountId: 'A', createdAt: 'x', updatedAt: 'x', metadata: { cost: { total_cost: 0 } } }, // keep
            { id: '4', itemId: 'i4', accountId: 'A', createdAt: 'x', updatedAt: 'x' } // drop
          ],
          nextToken: null
        }
      }
    })

    const res = await fetchCostAnalysisScoreResults({ accountId: 'A', hours: 24 })
    expect(res.items.map(r => r.id)).toEqual(['1', '3'])
  })

  test('paginates until hard cap of 1000', async () => {
    const page = (start: number, count: number) => Array.from({ length: count }, (_, i) => ({
      id: String(start + i), itemId: 'i', accountId: 'A', createdAt: 'x', updatedAt: 'x', cost: { total_cost: 0 }
    }))

    mockedRequest
      .mockResolvedValueOnce({
        data: { listScoreResultByAccountIdAndUpdatedAt: { items: page(1, 600), nextToken: 't1' } }
      })
      .mockResolvedValueOnce({
        data: { listScoreResultByAccountIdAndUpdatedAt: { items: page(601, 600), nextToken: null } }
      })

    const res = await fetchCostAnalysisScoreResults({ accountId: 'A', hours: 24 })
    expect(res.items.length).toBe(1000)
    expect(res.items[0].id).toBe('1')
    expect(res.items[999].id).toBe('1000')
  })

  test('requires required variable based on query selection', async () => {
    await expect(fetchCostAnalysisScoreResults({ hours: 24 })).rejects.toThrow('Missing required parameter: accountId')
  })

  test('client-side filters by scoreId when provided', async () => {
    mockedRequest.mockResolvedValueOnce({
      data: {
        listScoreResultByAccountIdAndUpdatedAt: {
          items: [
            { id: '1', itemId: 'i1', accountId: 'A', scoreId: 'S1', createdAt: 'x', updatedAt: 'x', cost: { total_cost: 0 } },
            { id: '2', itemId: 'i2', accountId: 'A', scoreId: 'S2', createdAt: 'x', updatedAt: 'x', cost: { total_cost: 0 } }
          ],
          nextToken: null
        }
      }
    })

    const res = await fetchCostAnalysisScoreResults({ accountId: 'A', scoreId: 'S1', hours: 24 })
    expect(res.items.map(r => r.id)).toEqual(['1'])
  })
})



import { graphqlRequest, handleGraphQLErrors } from './amplify-client'

export interface ScoreResultRecord {
  id: string
  itemId: string
  accountId: string
  scorecardId?: string | null
  scoreId?: string | null
  code?: string | null
  type?: string | null
  createdAt: string
  updatedAt: string
  value?: any
  score?: { id?: string | null; name?: string | null } | null
  cost?: any
  metadata?: any
}

export interface FetchCostAnalysisOptions {
  accountId?: string
  scorecardId?: string
  scoreId?: string
  days?: number
  hours?: number | null
  limit?: number // hard cap across pages (default 1000)
}

export interface FetchCostAnalysisResult {
  items: ScoreResultRecord[]
  window: { startTime: string; endTime: string; hours?: number | null; days?: number | null }
}

function ensureObject(value: any): Record<string, any> | null {
  if (value == null) return null
  if (typeof value === 'object') return value as Record<string, any>
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, any>) : null
    } catch {
      return null
    }
  }
  return null
}

function extractCost(sr: ScoreResultRecord): Record<string, any> | null {
  // Prefer explicit top-level cost; fallback to metadata.cost
  const top = ensureObject(sr.cost)
  if (top && Object.keys(top).length > 0) return top
  const meta = ensureObject(sr.metadata) || {}
  const metaCost = ensureObject((meta as any).cost)
  if (metaCost && Object.keys(metaCost).length > 0) return metaCost
  return null
}

function computeWindow(days?: number, hours?: number | null): { startTime: string; endTime: string; hours?: number | null; days?: number | null } {
  // Default to last 24 hours per requirement
  const now = new Date()
  let start: Date
  if (hours == null) {
    const d = Number.isFinite(days) && days && days > 0 ? Math.floor(days) : 1
    start = new Date(now.getTime() - d * 24 * 60 * 60 * 1000)
  } else {
    const h = hours && hours > 0 ? Math.floor(hours) : 24
    start = new Date(now.getTime() - h * 60 * 60 * 1000)
  }
  return { startTime: start.toISOString(), endTime: now.toISOString(), hours, days }
}

function buildQuery(params: { accountId?: string; scorecardId?: string; scoreId?: string }): {
  query: string
  topKey: string
  variableNames: string[]
} {
  if (params.scorecardId) {
    const topKey = 'listScoreResultByScorecardIdAndUpdatedAt'
    const query = `
      query GetScoreResultsByScorecard($scorecardId: String!, $startTime: String!, $endTime: String!, $nextToken: String, $limit: Int) {
        ${topKey}(
          scorecardId: $scorecardId,
          updatedAt: { between: [$startTime, $endTime] },
          nextToken: $nextToken,
          limit: $limit
        ) {
          items {
            id value itemId accountId scorecardId scoreId code type createdAt updatedAt
            score { id name }
            cost
            metadata
          }
          nextToken
        }
      }
    `
    return { query, topKey, variableNames: ['scorecardId'] }
  }
  // Default by account
  const topKey = 'listScoreResultByAccountIdAndUpdatedAt'
  const query = `
    query GetScoreResultsByAccount($accountId: String!, $startTime: String!, $endTime: String!, $nextToken: String, $limit: Int) {
      ${topKey}(
        accountId: $accountId,
        updatedAt: { between: [$startTime, $endTime] },
        nextToken: $nextToken,
        limit: $limit
      ) {
        items {
          id value itemId accountId scorecardId scoreId code type createdAt updatedAt
          score { id name }
          cost
          metadata
        }
        nextToken
      }
    }
  `
  return { query, topKey, variableNames: ['accountId'] }
}

/**
 * Fetch ScoreResults for cost analysis using GSIs with pagination.
 * - Defaults to last 24 hours
 * - Hard caps total returned records to 1000
 * - Filters out records with no cost information (zero is valid information)
 */
export async function fetchCostAnalysisScoreResults(options: FetchCostAnalysisOptions = {}): Promise<FetchCostAnalysisResult> {
  const hardLimit = options.limit && options.limit > 0 ? Math.min(options.limit, 1000) : 1000
  const window = computeWindow(options.days, options.hours ?? 24)

  const { query, topKey, variableNames } = buildQuery({
    accountId: options.accountId,
    scorecardId: options.scorecardId,
    scoreId: options.scoreId,
  })

  // Validate required variable for the chosen query
  const variables: Record<string, any> = {
    startTime: window.startTime,
    endTime: window.endTime,
    limit: Math.min(hardLimit, 1000),
  }
  for (const key of variableNames) {
    const v = (options as any)[key]
    if (!v) {
      throw new Error(`Missing required parameter: ${key}`)
    }
    variables[key] = v
  }

  let nextToken: string | null | undefined = null
  const all: ScoreResultRecord[] = []
  const filterScoreId: string | undefined = options.scoreId

  do {
    const resp = await graphqlRequest<{ [k: string]: { items: ScoreResultRecord[]; nextToken?: string | null } }>(query, {
      ...variables,
      nextToken,
    })
    handleGraphQLErrors(resp)
    const data = resp.data as any
    const payload = data?.[topKey] || {}
    const pageItems: ScoreResultRecord[] = Array.isArray(payload.items) ? payload.items : []
    for (const sr of pageItems) {
      if (filterScoreId && String(sr.scoreId) !== String(filterScoreId)) {
        continue
      }
      if (extractCost(sr)) {
        all.push(sr)
      }
      if (all.length >= hardLimit) break
    }
    nextToken = payload.nextToken
  } while (nextToken && all.length < hardLimit)

  return { items: all.slice(0, hardLimit), window }
}

export const __testUtils = { ensureObject, extractCost, buildQuery, computeWindow, aggregateCostByScore }

// ---------- Aggregations to match Python-style per score breakdown ----------

export interface CostSummary {
  count: number
  total_cost: number
  average_cost: number
  average_calls: number
}

export interface CostGroupSummary extends CostSummary {
  group: { scoreId?: string; scorecardId?: string; scoreName?: string }
}

export interface CostAnalysisAggregates {
  summary: CostSummary
  groups: CostGroupSummary[]
}

export function aggregateCostByScore(items: ScoreResultRecord[]): CostAnalysisAggregates {
  const perScore: Record<string, { name?: string; count: number; total: number; calls: number }> = {}
  let overallCount = 0
  let overallTotal = 0
  let overallCalls = 0

  for (const sr of items) {
    const cost = extractCost(sr)
    if (!cost) continue
    const total = Number((cost as any).total_cost ?? 0)
    const calls = Number((cost as any).llm_calls ?? 0)
    const sId = String(sr.scoreId || '')
    if (!perScore[sId]) perScore[sId] = { name: sr.score?.name || undefined, count: 0, total: 0, calls: 0 }
    perScore[sId].count += 1
    perScore[sId].total += Number.isFinite(total) ? total : 0
    perScore[sId].calls += Number.isFinite(calls) ? calls : 0
    overallCount += 1
    overallTotal += Number.isFinite(total) ? total : 0
    overallCalls += Number.isFinite(calls) ? calls : 0
  }

  const groups: CostGroupSummary[] = Object.entries(perScore).map(([scoreId, stats]) => ({
    group: { scoreId, scoreName: stats.name },
    count: stats.count,
    total_cost: stats.total,
    average_cost: stats.count ? stats.total / stats.count : 0,
    average_calls: stats.count ? stats.calls / stats.count : 0,
  }))

  groups.sort((a, b) => (a.group.scoreId || '').localeCompare(b.group.scoreId || ''))

  const summary: CostSummary = {
    count: overallCount,
    total_cost: overallTotal,
    average_cost: overallCount ? overallTotal / overallCount : 0,
    average_calls: overallCount ? overallCalls / overallCount : 0,
  }

  return { summary, groups }
}



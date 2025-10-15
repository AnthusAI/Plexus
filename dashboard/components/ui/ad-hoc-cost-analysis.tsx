"use client"

import React, { useEffect, useMemo, useState } from 'react'
import { useAccount } from '@/app/contexts/AccountContext'
import { fetchCostAnalysisScoreResults, aggregateCostByScore, type ScoreResultRecord } from '@/utils/cost-analysis'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Loader2, RefreshCw } from 'lucide-react'
import { CostAnalysisDisplay, type CostAnalysisDisplayData } from '@/components/ui/cost-analysis-display'

export interface AdHocCostAnalysisProps {
  scorecardId?: string
  scoreId?: string
  defaultHours?: number | null
  defaultDays?: number | null
}

function ensureObject(value: any): Record<string, any> | null {
  if (value == null) return null
  if (typeof value === 'object') return value
  if (typeof value === 'string') {
    try { const parsed = JSON.parse(value); return typeof parsed === 'object' && parsed !== null ? parsed : null } catch { return null }
  }
  return null
}

function extractCost(sr: ScoreResultRecord): Record<string, any> | null {
  const top = ensureObject(sr.cost)
  if (top && Object.keys(top).length > 0) return top
  const meta = ensureObject(sr.metadata) || {}
  const metaCost = ensureObject((meta as any).cost)
  return metaCost && Object.keys(metaCost).length > 0 ? metaCost : null
}

export const AdHocCostAnalysis: React.FC<AdHocCostAnalysisProps> = ({ scorecardId, scoreId, defaultHours = 24, defaultDays = null }) => {
  const { selectedAccount } = useAccount()
  const [hours, setHours] = useState<number | null>(defaultHours)
  const [days, setDays] = useState<number | null>(defaultDays)
  const [limit, setLimit] = useState<number>(200)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [records, setRecords] = useState<ScoreResultRecord[] | null>(null)

  const load = async () => {
    if (!selectedAccount?.id) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetchCostAnalysisScoreResults({
        accountId: selectedAccount.id,
        scorecardId,
        scoreId,
        hours: hours ?? undefined,
        days: days ?? undefined,
        limit: limit,
      })
      setRecords(res.items)
    } catch (e: any) {
      setError(e?.message || 'Failed to load cost analysis')
      setRecords(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() // initial
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAccount?.id, scorecardId, scoreId, limit])

  const data: CostAnalysisDisplayData | null = useMemo(() => {
    if (!records) return null
    const { summary, groups, itemAnalysis } = aggregateCostByScore(records)

    return {
      summary: {
        count: summary.count,
        total_cost: String(summary.total_cost),
        average_cost: String(summary.average_cost),
        average_calls: summary.average_calls,
      },
      groups: groups.map(g => ({
        group: g.group,
        count: g.count,
        total_cost: String(g.total_cost),
        average_cost: String(g.average_cost),
        average_calls: g.average_calls,
        min_cost: g.min_cost,
        q1_cost: g.q1_cost,
        median_cost: g.median_cost,
        q3_cost: g.q3_cost,
        max_cost: g.max_cost,
        values: g.values,
      })),
      itemAnalysis: {
        count: itemAnalysis.count,
        total_cost: itemAnalysis.total_cost,
        average_cost: itemAnalysis.average_cost,
        average_calls: itemAnalysis.average_calls,
      },
      window: { hours: hours ?? undefined, days: days ?? undefined },
      filters: { scorecardId, scoreId }
    }
  }, [records, hours, days, scorecardId, scoreId])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-3">
        <Select value={String(hours ?? 24)} onValueChange={(v) => { setHours(parseInt(v)); setDays(null); }} disabled={loading}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Hours" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="1">Last 1 hour</SelectItem>
            <SelectItem value="6">Last 6 hours</SelectItem>
            <SelectItem value="12">Last 12 hours</SelectItem>
            <SelectItem value="24">Last 24 hours</SelectItem>
            <SelectItem value="48">Last 48 hours</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1">
          <label htmlFor="limit-input" className="text-sm text-muted-foreground">Limit:</label>
          <Input
            id="limit-input"
            type="number"
            value={limit}
            onChange={(e) => setLimit(Math.max(1, Math.min(1000, parseInt(e.target.value) || 200)))}
            disabled={loading}
            className="w-20 h-8"
            min="1"
            max="1000"
          />
        </div>
        <Button variant="ghost" size="icon" onClick={load} disabled={loading} className="h-8 w-8 rounded-md border-0 shadow-none bg-border" aria-label="Refresh cost analysis">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
      </div>

      {error && (
        <Card className="mb-3">
          <CardContent className="text-destructive py-4">{error}</CardContent>
        </Card>
      )}

      {!error && !data && (
        <Card>
          <CardContent className="flex items-center justify-center py-8">
            <div className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Loading cost data...</span>
            </div>
          </CardContent>
        </Card>
      )}

      {data && (
        <CostAnalysisDisplay data={data} />
      )}
    </div>
  )
}

export default AdHocCostAnalysis



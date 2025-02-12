"use client"
import React, { useMemo, useCallback, useRef } from "react"
import { useState, useEffect } from "react"
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { EvaluationDashboardSkeleton } from "@/components/loading-skeleton"
import { ModelListResult, AmplifyListResult, AmplifyGetResult } from '@/types/shared'
import { listFromModel } from "@/utils/amplify-helpers"
import { useAuthenticator } from '@aws-amplify/ui-react'
import { useRouter } from 'next/navigation'
import { getClient } from '@/utils/amplify-client'
import { TaskDispatchButton, evaluationsConfig } from '@/components/task-dispatch'
import { EvaluationCard, EvaluationGrid } from '@/features/evaluations'
import { useEvaluationSubscriptions, useTaskUpdates } from '@/features/evaluations'
import { formatStatus, getBadgeVariant, calculateProgress } from '@/features/evaluations'

const ACCOUNT_KEY = 'call-criteria'

export default function EvaluationsDashboard() {
  const { user } = useAuthenticator()
  const router = useRouter()
  const [accountId, setAccountId] = useState<string | null>(null)
  const [evaluations, setEvaluations] = useState<Schema['Evaluation']['type'][]>([])
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null)
  const [scorecardNames, setScorecardNames] = useState<Record<string, string>>({})
  const [scoreNames, setScoreNames] = useState<Record<string, string>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch account ID
  useEffect(() => {
    const fetchAccountId = async () => {
      try {
        console.log('Fetching account ID...')
        const client = getClient()
        const accountResponse = await client.models.Account.list({
          filter: { key: { eq: ACCOUNT_KEY } }
        })
        console.log('Account response:', accountResponse)
        if (accountResponse.data?.length) {
          const id = accountResponse.data[0].id
          console.log('Found account ID:', id)
          setAccountId(id)
        } else {
          console.warn('No account found with key:', ACCOUNT_KEY)
          setError('No account found')
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error fetching account:', error)
        setError('Error fetching account')
        setIsLoading(false)
      }
    }
    fetchAccountId()
  }, [])

  // Fetch evaluations
  useEffect(() => {
    if (!accountId) return

    const fetchEvaluations = async () => {
      try {
        console.log('Fetching evaluations for account:', accountId)
        const client = getClient()
        const evaluationsResponse = await client.models.Evaluation.list({
          filter: { accountId: { eq: accountId } },
          sortDirection: 'DESC'
        })
        console.log('Evaluations response:', evaluationsResponse)
        if (evaluationsResponse.data) {
          console.log('Found evaluations:', evaluationsResponse.data.length)
          setEvaluations(evaluationsResponse.data)
        }
        setIsLoading(false)
      } catch (error) {
        console.error('Error fetching evaluations:', error)
        setError('Error fetching evaluations')
        setIsLoading(false)
      }
    }

    fetchEvaluations()
  }, [accountId])

  // Fetch scorecard and score names
  useEffect(() => {
    if (!accountId) return

    const fetchNames = async () => {
      try {
        console.log('Fetching scorecard names for account:', accountId)
        const client = getClient()
        const scorecardsResponse = await client.models.Scorecard.list({
          filter: { accountId: { eq: accountId } }
        })
        console.log('Scorecards response:', scorecardsResponse)
        const newScorecardNames: Record<string, string> = {}
        const newScoreNames: Record<string, string> = {}

        for (const scorecard of scorecardsResponse.data || []) {
          newScorecardNames[scorecard.id] = scorecard.name
          const sectionsResponse = await scorecard.sections()
          for (const section of sectionsResponse.data || []) {
            const scoresResponse = await section.scores()
            for (const score of scoresResponse.data || []) {
              newScoreNames[score.id] = score.name
            }
          }
        }

        console.log('Found scorecard names:', Object.keys(newScorecardNames).length)
        console.log('Found score names:', Object.keys(newScoreNames).length)
        setScorecardNames(newScorecardNames)
        setScoreNames(newScoreNames)
      } catch (error) {
        console.error('Error fetching names:', error)
        setError('Error fetching scorecard names')
      }
    }

    fetchNames()
  }, [accountId])

  // Subscribe to evaluation updates
  useEvaluationSubscriptions({
    accountId,
    onEvaluationUpdate: (updatedEvaluation) => {
      console.log('Received evaluation update:', updatedEvaluation.id)
      setEvaluations(prev => prev.map(evaluation => 
        evaluation.id === updatedEvaluation.id ? updatedEvaluation : evaluation
      ))
    },
    onEvaluationCreate: (newEvaluation) => {
      console.log('Received new evaluation:', newEvaluation.id)
      setEvaluations(prev => [newEvaluation, ...prev])
    },
    onEvaluationDelete: (evaluationId) => {
      console.log('Received evaluation deletion:', evaluationId)
      setEvaluations(prev => prev.filter(evaluation => evaluation.id !== evaluationId))
    }
  })

  const handleDelete = async (evaluationId: string) => {
    try {
      const currentClient = getClient()
      await currentClient.models.Evaluation.delete({ id: evaluationId })
      setEvaluations(prev => prev.filter(evaluation => evaluation.id !== evaluationId))
      if (selectedEvaluationId === evaluationId) {
        setSelectedEvaluationId(null)
      }
      return true
    } catch (error) {
      console.error('Error deleting evaluation:', error)
      return false
    }
  }

  if (isLoading) {
    return (
      <div>
        <div className="mb-4 text-sm text-muted-foreground">
          {error ? `Error: ${error}` : 'Loading evaluations...'}
        </div>
        <EvaluationDashboardSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Evaluations</h1>
        </div>
        <div className="text-sm text-destructive">Error: {error}</div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Evaluations</h1>
        <TaskDispatchButton config={evaluationsConfig} />
      </div>

      {evaluations.length === 0 ? (
        <div className="text-sm text-muted-foreground">No evaluations found</div>
      ) : (
        <EvaluationGrid
          evaluations={evaluations}
          selectedEvaluationId={selectedEvaluationId}
          scorecardNames={scorecardNames}
          scoreNames={scoreNames}
          onSelect={(evaluation) => setSelectedEvaluationId(evaluation.id)}
          onDelete={handleDelete}
        />
      )}
    </div>
  )
} 
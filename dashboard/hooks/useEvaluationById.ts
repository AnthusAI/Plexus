"use client"

import { useState, useEffect, useRef } from 'react'
import { generateClient } from 'aws-amplify/api'
import { Schema } from '@/amplify/data/resource'
import { transformEvaluation } from '@/utils/data-operations'
import type { Evaluation } from '@/utils/data-operations'

interface UseEvaluationByIdReturn {
  evaluation: Evaluation | null
  isLoading: boolean
  error: string | null
}

async function fetchEvaluationById(id: string): Promise<Evaluation> {
  const client = generateClient<Schema>()

  // Fetch the evaluation record
  // @ts-ignore - Bypass TypeScript's type checking for this specific call
  const response = await client.models.Evaluation.get({ id })
  const evaluationData = response.data

  if (!evaluationData) {
    throw new Error('Evaluation not found')
  }

  // Fetch all score results via paginated query
  let nextToken: string | null = null
  let scoreResultItems: any[] = []
  do {
    const resp = await client.graphql({
      query: `
        query ($evaluationId: String!, $limit: Int, $nextToken: String) {
          listScoreResultByEvaluationId(
            evaluationId: $evaluationId
            limit: $limit
            nextToken: $nextToken
          ) {
            items {
              id value explanation confidence metadata trace itemId createdAt
              feedbackItem { id editCommentValue initialAnswerValue initialCommentValue finalAnswerValue editorName editedAt createdAt scoreResults { items { id value explanation type } } }
              item { id itemIdentifiers { items { name value url position } } }
            }
            nextToken
          }
        }
      `,
      variables: { evaluationId: id, limit: 1000, nextToken }
    }) as any
    const data = resp?.data?.listScoreResultByEvaluationId
    scoreResultItems = scoreResultItems.concat(Array.isArray(data?.items) ? data.items : [])
    nextToken = data?.nextToken || null
  } while (nextToken)

  const evaluationWithResults = { ...evaluationData, scoreResults: { items: scoreResultItems } }
  const transformed = transformEvaluation(evaluationWithResults as any)
  if (!transformed) throw new Error('Failed to transform evaluation data')
  return transformed as Evaluation
}

export function useEvaluationById(evaluationId: string | null): UseEvaluationByIdReturn {
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const cacheRef = useRef<Map<string, Evaluation>>(new Map())

  useEffect(() => {
    if (!evaluationId) {
      setEvaluation(null)
      setIsLoading(false)
      setError(null)
      return
    }

    const cached = cacheRef.current.get(evaluationId)
    if (cached) {
      setEvaluation(cached)
      setIsLoading(false)
      setError(null)
      return
    }

    let cancelled = false

    const doFetch = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const data = await fetchEvaluationById(evaluationId)
        if (!cancelled) {
          cacheRef.current.set(evaluationId, data)
          setEvaluation(data)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to fetch evaluation')
          setEvaluation(null)
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    doFetch()
    return () => { cancelled = true }
  }, [evaluationId])

  return { evaluation, isLoading, error }
}

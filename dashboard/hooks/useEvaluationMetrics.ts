"use client"

import { useState, useEffect } from 'react'
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"

const client = generateClient<Schema>()

interface EvaluationMetrics {
  alignment: number | null  // Converted to 0-100 scale
  accuracy: number | null   // Already in 0-100 scale
}

interface UseEvaluationMetricsReturn {
  metrics: EvaluationMetrics | null
  isLoading: boolean
  error: string | null
}

/**
 * Custom hook to fetch evaluation metrics by evaluation ID
 *
 * @param evaluationId - The ID of the evaluation to fetch
 * @returns Object containing metrics, loading state, and error
 *
 * Metrics transformation:
 * - Alignment: Converted from Gwet's AC1 [-1, 1] to percentage [0, 100]
 * - Accuracy: Already in percentage format [0, 100]
 */
export function useEvaluationMetrics(evaluationId: string | null): UseEvaluationMetricsReturn {
  const [metrics, setMetrics] = useState<EvaluationMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Reset state if no evaluation ID
    if (!evaluationId) {
      setMetrics(null)
      setIsLoading(false)
      setError(null)
      return
    }

    const fetchEvaluationMetrics = async () => {
      try {
        setIsLoading(true)
        setError(null)

        const result = await client.graphql({
          query: `
            query GetEvaluation($id: ID!) {
              getEvaluation(id: $id) {
                id
                accuracy
                metrics
              }
            }
          `,
          variables: { id: evaluationId }
        })

        const evaluation = (result as any).data?.getEvaluation

        if (!evaluation) {
          setError('Evaluation not found')
          setMetrics(null)
          return
        }

        // Parse metrics array
        let metricsArray: Array<{ name: string; value: number }> = []
        try {
          if (typeof evaluation.metrics === 'string') {
            metricsArray = JSON.parse(evaluation.metrics)
          } else if (Array.isArray(evaluation.metrics)) {
            metricsArray = evaluation.metrics
          }
        } catch (parseError) {
          console.error('Error parsing evaluation metrics:', parseError)
        }

        // Extract alignment from metrics array
        const alignmentMetric = metricsArray.find(m => m.name === 'Alignment')
        let alignmentValue: number | null = null

        if (alignmentMetric !== undefined && alignmentMetric.value !== null) {
          // Convert Gwet's AC1 from [-1, 1] to [0, 100]
          alignmentValue = (alignmentMetric.value + 1) * 50
        }

        // Extract accuracy (already in 0-100 format)
        const accuracyValue = evaluation.accuracy !== null && evaluation.accuracy !== undefined
          ? evaluation.accuracy
          : null

        setMetrics({
          alignment: alignmentValue,
          accuracy: accuracyValue
        })
      } catch (err) {
        console.error('Error fetching evaluation metrics:', err)
        setError(err instanceof Error ? err.message : 'Failed to fetch evaluation metrics')
        setMetrics(null)
      } finally {
        setIsLoading(false)
      }
    }

    fetchEvaluationMetrics()
  }, [evaluationId])

  return { metrics, isLoading, error }
}

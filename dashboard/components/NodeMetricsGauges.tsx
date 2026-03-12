"use client"

import React from 'react'
import { Gauge } from './gauge'
import BeforeAfterGauges from './BeforeAfterGauges'
import { useEvaluationMetrics } from '@/hooks/useEvaluationMetrics'
import type { Schema } from "@/amplify/data/resource"

type GraphNode = Schema['GraphNode']['type']

interface NodeMetricsGaugesProps {
  node: GraphNode
  parentNode?: GraphNode | null
}

/**
 * Component to display evaluation metrics (Alignment and Accuracy) for Graph Nodes
 *
 * - Root nodes: Show single-value gauges (baseline)
 * - Child nodes: Show before/after gauges comparing parent metrics to child metrics
 * - Only renders when evaluation_id exists in node metadata
 */
export default function NodeMetricsGauges({ node, parentNode }: NodeMetricsGaugesProps) {
  // Parse node metadata to extract evaluation_id
  let nodeMetadata: any = {}
  try {
    if (typeof node.metadata === 'string') {
      nodeMetadata = JSON.parse(node.metadata)
    } else if (node.metadata) {
      nodeMetadata = node.metadata
    }
  } catch (error) {
    console.error('Error parsing node metadata:', error)
    return null
  }

  const evaluationId = nodeMetadata.evaluation_id || nodeMetadata.evaluationId

  // Don't render if no evaluation ID
  if (!evaluationId) {
    return null
  }

  // Fetch evaluation metrics for current node
  const { metrics: nodeMetrics, isLoading: nodeLoading, error: nodeError } = useEvaluationMetrics(evaluationId)

  // Parse parent metadata if parent node exists
  let parentEvaluationId: string | null = null
  if (parentNode) {
    try {
      let parentMetadata: any = {}
      if (typeof parentNode.metadata === 'string') {
        parentMetadata = JSON.parse(parentNode.metadata)
      } else if (parentNode.metadata) {
        parentMetadata = parentNode.metadata
      }
      parentEvaluationId = parentMetadata.evaluation_id || parentMetadata.evaluationId || null
    } catch (error) {
      console.error('Error parsing parent node metadata:', error)
    }
  }

  // Fetch parent evaluation metrics if parent has evaluation
  const { metrics: parentMetrics, isLoading: parentLoading } = useEvaluationMetrics(parentEvaluationId)

  // Show loading state
  if (nodeLoading || (parentNode && parentEvaluationId && parentLoading)) {
    return (
      <div className="flex gap-3 items-center">
        <div className="h-32 w-40 bg-muted animate-pulse rounded-lg" />
        <div className="h-32 w-40 bg-muted animate-pulse rounded-lg" />
      </div>
    )
  }

  // Don't render if there was an error or no metrics
  if (nodeError || !nodeMetrics) {
    return null
  }

  const isRootNode = !parentNode || !parentEvaluationId || !parentMetrics

  // Standard gauge segments
  const gaugeSegments = [
    { start: 0, end: 60, color: 'var(--gauge-inviable)' },
    { start: 60, end: 80, color: 'var(--gauge-converging)' },
    { start: 80, end: 90, color: 'var(--gauge-almost)' },
    { start: 90, end: 95, color: 'var(--gauge-viable)' },
    { start: 95, end: 100, color: 'var(--gauge-great)' },
  ]

  if (isRootNode) {
    // Root node: Show single-value gauges
    return (
      <div className="flex gap-3">
        {nodeMetrics.alignment !== null && (
          <div className="w-40">
            <Gauge
              value={nodeMetrics.alignment}
              title="Alignment"
              segments={gaugeSegments}
              min={0}
              max={100}
              valueUnit="%"
              decimalPlaces={1}
            />
          </div>
        )}
        {nodeMetrics.accuracy !== null && (
          <div className="w-40">
            <Gauge
              value={nodeMetrics.accuracy}
              title="Accuracy"
              segments={gaugeSegments}
              min={0}
              max={100}
              valueUnit="%"
              decimalPlaces={1}
            />
          </div>
        )}
      </div>
    )
  }

  // Child node: Show before/after gauges
  return (
    <div className="flex gap-3">
      {nodeMetrics.alignment !== null && parentMetrics.alignment !== null && (
        <div className="w-40">
          <BeforeAfterGauges
            title="Alignment"
            before={parentMetrics.alignment}
            after={nodeMetrics.alignment}
            segments={gaugeSegments}
            min={0}
            max={100}
            variant="bare"
          />
        </div>
      )}
      {nodeMetrics.accuracy !== null && parentMetrics.accuracy !== null && (
        <div className="w-40">
          <BeforeAfterGauges
            title="Accuracy"
            before={parentMetrics.accuracy}
            after={nodeMetrics.accuracy}
            segments={gaugeSegments}
            min={0}
            max={100}
            variant="bare"
          />
        </div>
      )}
    </div>
  )
}

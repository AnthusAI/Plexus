import React from 'react'
import { Schema } from '@/amplify/data/resource'
import { EvaluationCard } from './EvaluationCard'
import type { ProcessedEvaluation } from '@/utils/data-operations'

interface EvaluationGridProps {
  evaluations: ProcessedEvaluation[]
  selectedEvaluationId: string | undefined | null
  scorecardNames: Record<string, string>
  scoreNames: Record<string, string>
  onSelect: (evaluation: ProcessedEvaluation) => void
  onDelete: (evaluationId: string) => Promise<boolean>
  evaluationRefsMap?: React.MutableRefObject<Map<string, HTMLDivElement | null>>
}

export const EvaluationGrid = React.memo(({
  evaluations,
  selectedEvaluationId,
  scorecardNames,
  scoreNames,
  onSelect,
  onDelete,
  evaluationRefsMap
}: EvaluationGridProps) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {evaluations.map((evaluation) => (
        <EvaluationCard
          key={evaluation.id}
          evaluation={evaluation}
          selectedEvaluationId={selectedEvaluationId}
          scorecardNames={scorecardNames}
          scoreNames={scoreNames}
          onSelect={onSelect}
          onDelete={onDelete}
          evaluationRefsMap={evaluationRefsMap}
        />
      ))}
    </div>
  )
}) 
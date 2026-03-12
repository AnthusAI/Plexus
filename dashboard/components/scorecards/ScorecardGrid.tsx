"use client"
import React from 'react'
import type { Schema } from '@/amplify/data/resource'
import ScorecardComponent from './ScorecardComponent'

interface ScorecardGridProps {
  scorecards: (Schema['Scorecard']['type'] & { examples: string[] })[]
  scorecardScoreCounts: Record<string, number>
  scorecardCountsLoading: Record<string, boolean>
  selectedScorecardId?: string
  onSelectScorecard: (scorecard: Schema['Scorecard']['type'] | null) => void
  onEdit: (scorecard: Schema['Scorecard']['type']) => void
  onFeedbackAnalysis: (scorecardId: string) => void
  onCostAnalysis: (scorecardId: string) => void
  scorecardRefsMap: React.RefObject<Map<string, HTMLDivElement | null>>
}

const ScorecardGrid = React.memo(function ScorecardGrid({
  scorecards,
  scorecardScoreCounts,
  scorecardCountsLoading,
  selectedScorecardId,
  onSelectScorecard,
  onEdit,
  onFeedbackAnalysis,
  onCostAnalysis,
  scorecardRefsMap
}: ScorecardGridProps) {
  return (
    <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-4">
      {scorecards.map((scorecard) => {
        const scorecardData = {
          id: scorecard.id,
          name: scorecard.name,
          key: scorecard.key || '',
          description: scorecard.description || '',
          type: 'scorecard',
          order: 0,
          externalId: scorecard.externalId || '',
          scoreCount: scorecardScoreCounts[scorecard.id], // Keep undefined if not loaded yet
          isCountLoading: scorecardCountsLoading[scorecard.id] || false,
          examples: scorecard.examples || []
        }

        return (
          <div 
            key={scorecard.id}
            ref={(el) => {
              if (scorecardRefsMap.current) {
                scorecardRefsMap.current.set(scorecard.id, el)
              }
            }}
          >
            <ScorecardComponent
              variant="grid"
              score={scorecardData}
              isSelected={selectedScorecardId === scorecard.id}
              onClick={() => onSelectScorecard(scorecard)}
              onEdit={() => onEdit(scorecard)}
              onFeedbackAnalysis={() => onFeedbackAnalysis(scorecard.id)}
              onCostAnalysis={() => onCostAnalysis(scorecard.id)}
            />
          </div>
        )
      })}
    </div>
  )
}, (prevProps, nextProps) => {
  // Custom comparison for better performance
  return (
    prevProps.scorecards.length === nextProps.scorecards.length &&
    prevProps.selectedScorecardId === nextProps.selectedScorecardId &&
    JSON.stringify(prevProps.scorecardScoreCounts) === JSON.stringify(nextProps.scorecardScoreCounts) &&
    JSON.stringify(prevProps.scorecardCountsLoading) === JSON.stringify(nextProps.scorecardCountsLoading)
  )
})

export default ScorecardGrid
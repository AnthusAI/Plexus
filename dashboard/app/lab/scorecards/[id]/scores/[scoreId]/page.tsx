'use client'

import { useParams } from 'next/navigation'
import ScorecardsComponent from '@/components/scorecards-dashboard'

export default function ScoreDetailPage() {
  const params = useParams()
  const scorecardId = params.id as string
  const scoreId = params.scoreId as string
  
  return <ScorecardsComponent 
    initialSelectedScorecardId={scorecardId}
    initialSelectedScoreId={scoreId}
  />
} 
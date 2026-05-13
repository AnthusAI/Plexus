'use client'

import { useParams } from 'next/navigation'
import ScorecardsComponent from '@/components/scorecards-dashboard'

export default function ScoreVersionDetailPage() {
  const params = useParams()
  const scorecardId = params.id as string
  const scoreId = params.scoreId as string
  const versionId = params.versionId as string
  
  return <ScorecardsComponent 
    initialSelectedScorecardId={scorecardId}
    initialSelectedScoreId={scoreId}
    initialSelectedVersionId={versionId}
  />
}



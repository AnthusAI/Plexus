'use client'

import { useParams } from 'next/navigation'
import ScorecardsComponent from '@/components/scorecards-dashboard'

export default function ScorecardDetailPage() {
  const params = useParams()
  const scorecardId = params.id as string
  
  return <ScorecardsComponent initialSelectedScorecardId={scorecardId} />
} 
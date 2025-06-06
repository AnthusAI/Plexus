'use client'

import { useParams } from 'next/navigation'
import EvaluationsDashboard from '@/components/evaluations-dashboard'

export default function ScoreResultDetail() {
  const { id, scoreResultId } = useParams() as { id: string, scoreResultId: string }
  
  return <EvaluationsDashboard 
    initialSelectedEvaluationId={id} 
    initialSelectedScoreResultId={scoreResultId} 
  />
} 
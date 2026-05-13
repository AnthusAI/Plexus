'use client'

import { useParams } from 'next/navigation'
import EvaluationsDashboard from '@/components/evaluations-dashboard'

export default function LabEvaluationDetail() {
  const { id } = useParams() as { id: string }
  
  return <EvaluationsDashboard initialSelectedEvaluationId={id} />
} 
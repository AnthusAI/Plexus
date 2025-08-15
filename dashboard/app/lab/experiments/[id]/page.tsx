'use client'

import { useParams } from 'next/navigation'
import ExperimentsDashboard from '@/components/experiments-dashboard'

export default function LabExperimentDetail() {
  const { id } = useParams() as { id: string }
  
  return <ExperimentsDashboard initialSelectedExperimentId={id} />
}
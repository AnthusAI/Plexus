'use client'

import { useParams } from 'next/navigation'
import BatchesDashboard from '@/components/batches-dashboard'

export default function LabBatchDetail() {
  const { id } = useParams() as { id: string }
  
  return <BatchesDashboard initialSelectedBatchJobId={id} />
} 
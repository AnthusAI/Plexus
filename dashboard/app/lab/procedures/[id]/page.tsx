'use client'

import { use } from 'react'
import ProceduresDashboard from '@/components/procedures-dashboard'

interface Props {
  params: Promise<{ id: string }>
}

export default function LabProcedureDetail({ params }: Props) {
  const { id } = use(params)
  return <ProceduresDashboard initialSelectedProcedureId={id} />
}

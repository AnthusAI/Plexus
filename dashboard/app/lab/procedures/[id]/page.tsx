'use client'

import ProceduresDashboard from '@/components/procedures-dashboard'

interface Props {
  params: {
    id: string
  }
}

export default function LabProcedureDetail({ params }: Props) {
  return <ProceduresDashboard initialSelectedProcedureId={params.id} />
}

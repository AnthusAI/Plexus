'use client'

import { Suspense } from 'react'
import { useParams } from 'next/navigation'
import AssociatedDataSetsDashboard from '@/components/associated-datasets-dashboard'
import DataPageShell from '@/components/data-page-shell'
import { ScorecardDashboardSkeleton } from '@/components/loading-skeleton'

export default function DataSetPage() {
  const params = useParams()
  const id = params.id as string

  return (
    <Suspense fallback={<ScorecardDashboardSkeleton />}>
      <DataPageShell activeTab="datasets">
        <AssociatedDataSetsDashboard selectedDatasetId={id} pathBase="/lab/datasets" />
      </DataPageShell>
    </Suspense>
  )
}

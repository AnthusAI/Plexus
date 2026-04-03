'use client'

import { Suspense } from 'react'
import AssociatedDataSetsDashboard from '@/components/associated-datasets-dashboard'
import DataPageShell from '@/components/data-page-shell'
import { ScorecardDashboardSkeleton } from '@/components/loading-skeleton'

export default function DataSetsPage() {
  return (
    <Suspense fallback={<ScorecardDashboardSkeleton />}>
      <DataPageShell activeTab="datasets">
        <AssociatedDataSetsDashboard pathBase="/lab/datasets" />
      </DataPageShell>
    </Suspense>
  )
}

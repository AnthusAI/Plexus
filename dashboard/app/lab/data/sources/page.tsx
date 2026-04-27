'use client'

import { Suspense } from 'react'
import DataSourcesDashboard from '@/components/data-sources-dashboard'
import DataPageShell from '@/components/data-page-shell'
import { ScorecardDashboardSkeleton } from '@/components/loading-skeleton'

export default function DataSourcesPage() {
  return (
    <Suspense fallback={<ScorecardDashboardSkeleton />}>
      <DataPageShell activeTab="sources">
        <DataSourcesDashboard pathBase="/lab/data/sources" />
      </DataPageShell>
    </Suspense>
  )
}

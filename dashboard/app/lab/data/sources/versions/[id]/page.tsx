'use client'

import { Suspense } from 'react'
import { useParams } from 'next/navigation'
import DataSourcesDashboard from '@/components/data-sources-dashboard'
import DataPageShell from '@/components/data-page-shell'
import { ScorecardDashboardSkeleton } from '@/components/loading-skeleton'

export default function SourceVersionPage() {
  const params = useParams()
  const id = params.id as string

  return (
    <Suspense fallback={<ScorecardDashboardSkeleton />}>
      <DataPageShell activeTab="sources">
        <DataSourcesDashboard selectedVersionId={id} pathBase="/lab/data/sources" />
      </DataPageShell>
    </Suspense>
  )
}

"use client"

import { Suspense } from "react"
import { useParams } from "next/navigation"
import DataSourcesDashboard from "@/components/data-sources-dashboard"
import { ScorecardDashboardSkeleton } from "@/components/loading-skeleton"

export default function SourceVersionPage() {
  const params = useParams()
  const versionId = params.id as string

  return (
    <Suspense fallback={<ScorecardDashboardSkeleton />}>
      <DataSourcesDashboard selectedVersionId={versionId} />
    </Suspense>
  )
}
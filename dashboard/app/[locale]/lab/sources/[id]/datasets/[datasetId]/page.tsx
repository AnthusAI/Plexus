"use client"

import { Suspense } from "react"
import { useParams } from "next/navigation"
import DataSourcesDashboard from "@/components/data-sources-dashboard"
import { ScorecardDashboardSkeleton } from "@/components/loading-skeleton"

export default function SourceDatasetPage() {
  const params = useParams()
  const sourceId = params.id as string
  const datasetId = params.datasetId as string

  return (
    <Suspense fallback={<ScorecardDashboardSkeleton />}>
      <DataSourcesDashboard selectedSourceId={sourceId} selectedDatasetId={datasetId} />
    </Suspense>
  )
}
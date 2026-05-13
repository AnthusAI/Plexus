"use client"

import { Suspense } from "react"
import { useParams } from "next/navigation"
import DataSourcesDashboard from "@/components/data-sources-dashboard"
import { ScorecardDashboardSkeleton } from "@/components/loading-skeleton"

export default function SourcePage() {
  const params = useParams()
  const sourceId = params.id as string

  return (
    <Suspense fallback={<ScorecardDashboardSkeleton />}>
      <DataSourcesDashboard selectedSourceId={sourceId} />
    </Suspense>
  )
}
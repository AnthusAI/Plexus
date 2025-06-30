"use client"

import { Suspense } from "react"
import DataSourcesDashboard from "@/components/data-sources-dashboard"
import { ScorecardDashboardSkeleton } from "@/components/loading-skeleton"

export default function SourcesPage() {
  return (
    <Suspense fallback={<ScorecardDashboardSkeleton />}>
      <DataSourcesDashboard />
    </Suspense>
  )
}
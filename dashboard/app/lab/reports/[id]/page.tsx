import ReportsDashboard from '@/components/reports-dashboard'
import ReportArtifactViewer from '@/components/reports/ReportArtifactViewer'

export default async function ReportPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<{ revision?: string; artifact?: string }>
}) {
  const { id } = await params
  const query = await searchParams
  if (query.revision !== undefined || query.artifact !== undefined) {
    return (
      <ReportArtifactViewer
        reportId={id}
        revision={Number(query.revision)}
        logicalId={query.artifact || ''}
      />
    )
  }
  return <ReportsDashboard initialSelectedReportId={id} />
}

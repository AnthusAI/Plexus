import ReportsDashboard from '@/components/reports-dashboard'

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return <ReportsDashboard initialSelectedReportId={id} />
}

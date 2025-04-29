import ReportsDashboard from '@/components/reports-dashboard'

export default function ReportPage({ params }: { params: { id: string } }) {
  return <ReportsDashboard initialSelectedReportId={params.id} />
} 
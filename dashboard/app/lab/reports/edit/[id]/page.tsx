import { ReportConfigurationEdit } from "@/components/report-configuration-edit"

export default async function ReportConfigurationEditPage({
  params,
}: {
  params: Promise<{ id: string }> | { id: string }
}) {
  const resolvedParams = await params
  return <ReportConfigurationEdit id={resolvedParams?.id || ''} />
}

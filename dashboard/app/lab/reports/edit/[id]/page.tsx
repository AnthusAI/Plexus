import { ReportConfigurationEdit } from "@/components/report-configuration-edit"

export default async function ReportConfigurationEditPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return <ReportConfigurationEdit id={id} />
}

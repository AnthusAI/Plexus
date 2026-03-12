import { ReportConfigurationEdit } from "@/components/report-configuration-edit"

export default function ReportConfigurationEditPage({
  params,
}: {
  params: { id: string }
}) {
  return <ReportConfigurationEdit id={params.id} />
} 
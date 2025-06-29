import { Play } from "lucide-react"
import { TaskDispatchConfig } from "../types"
import { ReportConfigurationDialog } from "../dialogs/ReportConfigurationDialog"

export const createReportsConfig = (t: (key: string) => string): TaskDispatchConfig => ({
  buttonLabel: t('runReport'),
  actions: [
    {
      name: t('runReport'),
      icon: <Play className="mr-2 h-4 w-4" />,
      command: "report run", // Base command, will be extended with config ID
      target: "report",
      dialogType: "reportConfiguration",
      description: "Generate a report using a report configuration"
    }
  ],
  dialogs: {
    reportConfiguration: ReportConfigurationDialog
  }
}) 
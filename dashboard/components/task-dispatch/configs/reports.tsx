import React from "react"
import { Play } from "lucide-react"
import { TaskDispatchConfig } from "../types"
import { ReportConfigurationDialog } from "../dialogs/ReportConfigurationDialog"

export const reportsConfig: TaskDispatchConfig = {
  buttonLabel: "Run Report",
  actions: [
    {
      name: "Run Report",
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
} 
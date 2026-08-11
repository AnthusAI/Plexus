import React from "react"
import { FlaskConical } from "lucide-react"
import { TaskDispatchConfig } from "../types"
import { EvaluationDialog } from "../dialogs/EvaluationDialog"

export const activityConfig: TaskDispatchConfig = {
  buttonLabel: "Actions",
  actions: [
    {
      name: "Evaluate Accuracy",
      action: 'evaluation.accuracy',
      icon: <FlaskConical className="mr-2 h-4 w-4" />,
      command: "evaluate accuracy",
      target: "evaluation",
      dialogType: "evaluation"
    }
  ],
  dialogs: {
    evaluation: EvaluationDialog
  }
}

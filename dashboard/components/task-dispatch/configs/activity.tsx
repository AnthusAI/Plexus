import { PlayCircle, ClipboardCheck } from "lucide-react"
import { TaskDispatchConfig } from "../types"
import { SimpleDialog } from "../dialogs/SimpleDialog"
import { EvaluationDialog } from "../dialogs/EvaluationDialog"

export const activityConfig: TaskDispatchConfig = {
  buttonLabel: "Actions",
  actions: [
    {
      name: "Command",
      icon: <PlayCircle className="mr-2 h-4 w-4" />,
      command: "command demo",
      dialogType: "simple"
    },
    {
      name: "Accuracy",
      icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
      command: "evaluate accuracy",
      target: "evaluation",
      dialogType: "evaluation"
    },
    {
      name: "Consistency",
      icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
      command: "evaluate consistency",
      target: "evaluation",
      dialogType: "evaluation"
    },
    {
      name: "Alignment",
      icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
      command: "evaluate alignment",
      target: "evaluation",
      dialogType: "evaluation"
    }
  ],
  dialogs: {
    simple: SimpleDialog,
    evaluation: EvaluationDialog
  }
} 
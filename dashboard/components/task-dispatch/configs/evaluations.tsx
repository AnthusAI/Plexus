import { ClipboardCheck } from "lucide-react"
import { TaskDispatchConfig } from "../types"
import { EvaluationDialog } from "../dialogs/EvaluationDialog"

export const evaluationsConfig: TaskDispatchConfig = {
  buttonLabel: "Run",
  actions: [
    {
      name: "Accuracy",
      icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
      command: "evaluate accuracy",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Evaluate model accuracy against ground truth"
    },
    {
      name: "Consistency",
      icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
      command: "evaluate consistency",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Evaluate model consistency across similar inputs"
    },
    {
      name: "Alignment",
      icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
      command: "evaluate alignment",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Evaluate model alignment with business objectives"
    }
  ],
  dialogs: {
    evaluation: EvaluationDialog
  }
} 
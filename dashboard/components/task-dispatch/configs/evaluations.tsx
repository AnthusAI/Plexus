import { FlaskConical, FlaskRound, TestTubes } from "lucide-react"
import { TaskDispatchConfig } from "../types"
import { EvaluationDialog } from "../dialogs/EvaluationDialog"

export const evaluationsConfig: TaskDispatchConfig = {
  buttonLabel: "Run",
  actions: [
    {
      name: "Evaluate Accuracy",
      icon: <FlaskConical className="mr-2 h-4 w-4" />,
      command: "evaluate accuracy",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Evaluate model accuracy against ground truth"
    },
    {
      name: "Evaluate Consistency",
      icon: <FlaskRound className="mr-2 h-4 w-4" />,
      command: "evaluate consistency",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Evaluate model consistency across similar inputs"
    },
    {
      name: "Evaluate Alignment",
      icon: <TestTubes className="mr-2 h-4 w-4" />,
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
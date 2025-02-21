import { PlayCircle, FlaskConical, SquareTerminal, FlaskRound, TestTubes } from "lucide-react"
import { TaskDispatchConfig } from "../types"
import { SimpleDialog } from "../dialogs/SimpleDialog"
import { EvaluationDialog } from "../dialogs/EvaluationDialog"

export const activityConfig: TaskDispatchConfig = {
  buttonLabel: "Actions",
  actions: [
    {
      name: "Evaluate Accuracy",
      icon: <FlaskConical className="mr-2 h-4 w-4" />,
      command: "evaluate accuracy",
      target: "evaluation",
      dialogType: "evaluation"
    },
    {
      name: "Evaluate Consistency",
      icon: <FlaskRound className="mr-2 h-4 w-4" />,
      command: "evaluate consistency",
      target: "evaluation",
      dialogType: "evaluation"
    },
    {
      name: "Evaluate Alignment",
      icon: <TestTubes className="mr-2 h-4 w-4" />,
      command: "evaluate alignment",
      target: "evaluation",
      dialogType: "evaluation"
    },
    {
      name: "Run Command",
      icon: <SquareTerminal className="mr-2 h-4 w-4" />,
      command: "command demo",
      dialogType: "simple"
    }
  ],
  dialogs: {
    simple: SimpleDialog,
    evaluation: EvaluationDialog
  }
} 
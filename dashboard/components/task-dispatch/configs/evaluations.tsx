import { FlaskConical, FlaskRound, TestTubes } from "lucide-react"
import { TaskDispatchConfig } from "../types"
import { EvaluationDialog } from "../dialogs/EvaluationDialog"

export const createEvaluationsConfig = (t: (key: string) => string): TaskDispatchConfig => ({
  buttonLabel: t('run'),
  actions: [
    {
      name: t('evaluateAccuracy'),
      icon: <FlaskConical className="mr-2 h-4 w-4" />,
      command: "evaluate accuracy",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Evaluate model accuracy against ground truth"
    },
    {
      name: t('evaluateConsistency'),
      icon: <FlaskRound className="mr-2 h-4 w-4" />,
      command: "evaluate consistency",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Evaluate model consistency across similar inputs"
    },
    {
      name: t('evaluateAlignment'),
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
}) 
import ScoreTypeBadge from "@/components/ScoreTypeBadge"
import { SquareSplitVertical, Layers, Scale, EqualNot, Target, ShieldAlert } from 'lucide-react'

export const SCORE_TYPES = {
  binary: {
    key: 'binary',
    icon: SquareSplitVertical,
    label: "Binary",
    subLabel: "2 classes",
    color: "blue"
  },
  multiclass: {
    key: 'multiclass',
    icon: Layers,
    label: "Multi-class",
    subLabel: "3+ classes",
    color: "purple"
  }
}

export const DATA_BALANCES = {
  balanced: {
    key: 'balanced',
    icon: Scale,
    label: "Balanced",
    subLabel: "Equal distribution",
    color: "green"
  },
  unbalanced: {
    key: 'unbalanced',
    icon: EqualNot,
    label: "Unbalanced",
    subLabel: "Skewed distribution",
    color: "yellow"
  }
}

export const SCORE_GOALS = {
  recall: {
    key: 'recall',
    icon: Target,
    label: "Detect All Positives",
    subLabel: "High recall",
    color: "indigo"
  },
  precision: {
    key: 'precision',
    icon: ShieldAlert,
    label: "Avoid False Positives",
    subLabel: "High precision",
    color: "red"
  },
  balanced: {
    key: 'balanced',
    icon: Scale,
    label: "Balanced Approach",
    subLabel: "High F1-score",
    color: "orange"
  }
}

type ScoreTypesHeaderProps = {
  scoreType?: string
  dataBalance?: string
  scoreGoal?: string
}

export default function ScoreTypesHeader({ 
  scoreType,
  dataBalance,
  scoreGoal 
}: ScoreTypesHeaderProps) {
  const selectedType = scoreType ? SCORE_TYPES[scoreType as keyof typeof SCORE_TYPES] : undefined
  const selectedBalance = dataBalance ? DATA_BALANCES[dataBalance as keyof typeof DATA_BALANCES] : undefined
  const selectedGoal = scoreGoal ? SCORE_GOALS[scoreGoal as keyof typeof SCORE_GOALS] : undefined

  return (
    <div className="grid grid-cols-3 gap-4">
      {selectedType && (
        <ScoreTypeBadge
          icon={selectedType.icon}
          label={selectedType.label}
          subLabel={selectedType.subLabel}
          color={selectedType.color}
        />
      )}
      {selectedBalance && (
        <ScoreTypeBadge
          icon={selectedBalance.icon}
          label={selectedBalance.label}
          subLabel={selectedBalance.subLabel}
          color={selectedBalance.color}
        />
      )}
      {selectedGoal && (
        <ScoreTypeBadge
          icon={selectedGoal.icon}
          label={selectedGoal.label}
          subLabel={selectedGoal.subLabel}
          color={selectedGoal.color}
        />
      )}
    </div>
  )
} 
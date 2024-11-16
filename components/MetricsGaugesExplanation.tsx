import React from 'react'
import { Ruler, Radar, DraftingCompass, Scale, Goal } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

interface MetricsGaugesExplanationProps {
  explanation: string | null | undefined
  goal: string | null | undefined
}

const getGoalIcon = (goal: string) => {
  switch (goal.toLowerCase()) {
    case 'sensitivity':
      return <Radar className="w-3 h-3 mr-1" />
    case 'precision':
      return <DraftingCompass className="w-3 h-3 mr-1" />
    case 'balanced':
      return <Scale className="w-3 h-3 mr-1" />
    default:
      return null
  }
}

export default function MetricsGaugesExplanation({ 
  explanation, 
  goal 
}: MetricsGaugesExplanationProps) {
  if (!explanation) return null

  return (
    <div className="w-full mb-4">
      <div className="flex justify-between items-start mb-1">
        <div className="flex items-start">
          <Ruler className="w-4 h-4 mr-1 mt-0.5 text-foreground shrink-0" />
          <span className="text-sm text-foreground">Metrics</span>
        </div>
        {goal && (
          <div className="flex items-start text-right ml-auto">
            <span className="text-sm mr-1 text-foreground">Goal:</span>
            <Goal className="w-4 h-4 mt-0.5 text-foreground shrink-0" />
          </div>
        )}
      </div>
      <div className="grid grid-cols-[1fr,auto] gap-4">
        <p className="text-sm text-muted-foreground">
          {explanation}
        </p>
        {goal && (
          <div className="flex items-start">
            <Badge 
              variant="secondary" 
              className="flex items-center bg-background border-0"
            >
              {getGoalIcon(goal)}
              <span className="capitalize">{goal.toLowerCase()}</span>
            </Badge>
          </div>
        )}
      </div>
    </div>
  )
} 
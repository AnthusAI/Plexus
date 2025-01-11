import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LabelBadgeComparison } from '@/components/LabelBadgeComparison'

export interface EvaluationTaskScoreResultProps {
  id: string
  value: string
  confidence: number | null
  explanation: string | null
  metadata: {
    human_label: string | null
    correct: boolean
  }
  itemId: string | null
  isFocused?: boolean
}

export function EvaluationTaskScoreResult({ 
  value,
  confidence,
  explanation,
  metadata,
  isFocused
}: EvaluationTaskScoreResultProps) {
  return (
    <Card className={`px-0 pb-0 rounded-lg border-0 shadow-none transition-colors
      hover:bg-background
      ${isFocused ? 'bg-background' : 'bg-card-light'}`}>
      <CardContent className="flex flex-col p-2">
        <div className="flex items-start justify-between">
          <div>
            <div className="font-medium">
              <LabelBadgeComparison
                predictedLabel={value}
                actualLabel={metadata.human_label ?? ''}
                isCorrect={metadata.correct}
                showStatus={false}
                isFocused={isFocused}
              />
              {explanation && (
                <div className="text-sm text-muted-foreground mt-1 line-clamp-2">
                  {explanation}
                </div>
              )}
            </div>
          </div>
          {confidence && (
            <Badge className="bg-card self-start shadow-none">
              {Math.round(confidence * 100)}%
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
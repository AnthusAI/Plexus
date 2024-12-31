import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LabelBadgeComparison } from '@/components/LabelBadgeComparison'

export interface EvaluationTaskScoreResultProps {
  id: string
  value: string | number
  confidence?: number | null
  metadata?: any
  correct?: boolean | null
  isFocused?: boolean
}

export function EvaluationTaskScoreResult({ 
  value, 
  confidence, 
  metadata,
  correct,
  isFocused
}: EvaluationTaskScoreResultProps) {
  const parsedMetadata = typeof metadata === 'string' ? 
    JSON.parse(metadata) : metadata

  const firstResultKey = parsedMetadata?.results ? 
    Object.keys(parsedMetadata.results)[0] : null
  const result = firstResultKey ? 
    parsedMetadata.results[firstResultKey] : null

  return (
    <Card className={`px-0 pb-0 rounded-lg border-0 shadow-none transition-colors
      hover:bg-background
      ${isFocused ? 'bg-background' : 'bg-card-light'}`}>
      <CardContent className="flex flex-col p-2">
        <div className="flex items-start justify-between">
          <div>
            <div className="font-medium">
              {result?.metadata ? (
                <>
                  <LabelBadgeComparison
                    predictedLabel={result.value}
                    actualLabel={result.metadata.human_label}
                    isCorrect={result.metadata.correct}
                    showStatus={false}
                    isFocused={isFocused}
                  />
                  {result.explanation && (
                    <div className="text-sm text-muted-foreground mt-1 line-clamp-2">
                      {result.explanation}
                    </div>
                  )}
                </>
              ) : (
                'Unknown Prediction'
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
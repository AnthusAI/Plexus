import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ThumbsUp, ThumbsDown } from 'lucide-react'

export interface ExperimentTaskScoreResultProps {
  id: string
  value: number
  confidence?: number | null
  metadata?: any
  correct?: boolean | null
}

export function ExperimentTaskScoreResult({ 
  value, 
  confidence, 
  metadata,
  correct
}: ExperimentTaskScoreResultProps) {
  const parsedMetadata = typeof metadata === 'string' ? 
    JSON.parse(metadata) : metadata

  return (
    <Card className="px-0 pb-0 bg-card-light rounded-lg border-0 shadow-none">
      <CardContent className="flex flex-col p-2">
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-4">
            {correct !== null && (
              <div className="mt-1">
                {correct ? (
                  <ThumbsUp className="h-4 w-4 text-true" />
                ) : (
                  <ThumbsDown className="h-4 w-4 text-false" />
                )}
              </div>
            )}
            <div>
              <div className="font-medium">
                {parsedMetadata?.predicted_value || 'Unknown Prediction'}
              </div>
              <div className="text-sm text-muted-foreground">
                {parsedMetadata?.true_value && !correct && (
                  <span>Correct: {parsedMetadata.true_value}</span>
                )}
              </div>
            </div>
          </div>
          {confidence !== undefined && confidence !== null && (
            <Badge className="bg-card self-start shadow-none">
              {Math.round(confidence * 100)}% confident
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
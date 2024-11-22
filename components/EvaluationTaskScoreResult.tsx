import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ThumbsUp, ThumbsDown } from 'lucide-react'

export interface EvaluationTaskScoreResultProps {
  id: string
  value: number
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

  return (
    <Card className={`px-0 pb-0 rounded-lg border-0 shadow-none transition-colors
      hover:bg-background
      ${isFocused ? 'bg-background' : 'bg-card-light'}`}>
      <CardContent className="flex flex-col p-2">
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-4">
            {correct !== null && (
              <div className="mt-1">
                {correct ? (
                  <ThumbsUp className={`h-4 w-4 ${isFocused ? 'text-focus' : 'text-true'}`} />
                ) : (
                  <ThumbsDown className={`h-4 w-4 ${isFocused ? 'text-focus' : 'text-false'}`} />
                )}
              </div>
            )}
            <div>
              <div className="font-medium">
                {parsedMetadata?.predicted_value ? (
                  <span>
                    {correct ? (
                      <span className={isFocused ? 'text-focus' : ''}>
                        {parsedMetadata.predicted_value}
                      </span>
                    ) : (
                      <>
                        <span className={`line-through ${isFocused ? 'text-focus' : ''}`}>
                          {parsedMetadata.predicted_value}
                        </span>
                        <span className="ml-2 text-muted-foreground">
                          (<span className="text-muted-foreground">Correct: </span>
                          <span className={isFocused ? 'text-focus' : ''}>
                            {parsedMetadata.true_value}
                          </span>)
                        </span>
                      </>
                    )}
                  </span>
                ) : (
                  'Unknown Prediction'
                )}
              </div>
            </div>
          </div>
          {confidence !== undefined && confidence !== null && (
            <Badge className="bg-card self-start shadow-none">
              {Math.round(confidence * 100)}%
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
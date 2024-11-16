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
    <div className="p-4 bg-background rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          {correct !== null && (
            <div className="mr-2">
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
            {parsedMetadata?.true_value && (
              <div className="text-sm text-muted-foreground">
                Actual: {parsedMetadata.true_value}
              </div>
            )}
          </div>
        </div>
        {confidence !== undefined && confidence !== null && (
          <Badge variant="outline">
            {Math.round(confidence * 100)}% confident
          </Badge>
        )}
      </div>
    </div>
  )
} 
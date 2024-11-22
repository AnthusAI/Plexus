import React from 'react'
import { X, Microscope, CheckCircle, AlertTriangle, ArrowRight } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import { Badge } from '@/components/ui/badge'
import type { Schema } from "@/amplify/data/resource"

interface EvaluationTaskScoreResultDetailProps {
  result: Schema['ScoreResult']['type']
  onClose: () => void
  navigationControls?: React.ReactNode
}

export function EvaluationTaskScoreResultDetail({ 
  result, 
  onClose, 
  navigationControls 
}: EvaluationTaskScoreResultDetailProps) {
  const metadata = typeof result.metadata === 'string' ? 
    JSON.parse(result.metadata) : 
    result.metadata

  const isCorrect = result.value === 1

  return (
    <div className="relative -mt-1 h-full">
      <div className="absolute -top-4 right-0 z-10 flex items-center gap-2">
        {navigationControls}
        <CardButton icon={X} onClick={onClose} />
      </div>
      <div className="relative h-full">
        <div className="flex items-start mt-1">
          <Microscope className="w-4 h-4 mr-1 text-foreground shrink-0" />
          <span className="text-sm text-foreground">Score result</span>
        </div>
        <div className="bg-card-light rounded-lg p-4 pb-0 mt-1 h-[calc(100%-2rem)]">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Predicted</p>
                <div className="flex items-center">
                  <Badge 
                    variant="secondary"
                    className={`text-lg px-2 py-1 rounded-md text-focus ${
                      isCorrect 
                        ? "bg-true" 
                        : "bg-false"
                    }`}
                  >
                    {metadata?.predicted_value}
                  </Badge>
                  <div className="flex items-center ml-2">
                    {isCorrect ? (
                      <CheckCircle className="w-4 h-4 text-true mr-1" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-false mr-1" />
                    )}
                    <span className={`text-sm ${isCorrect ? "text-true" : "text-false"}`}>
                      {isCorrect ? "Correct" : "Incorrect"}
                    </span>
                  </div>
                </div>
              </div>
              {!isCorrect && (
                <ArrowRight className="w-5 h-5 text-muted-foreground mx-4" />
              )}
              <div className="text-right">
                <p className="text-sm text-muted-foreground mb-1">Actual</p>
                <Badge
                  variant="secondary"
                  className="text-lg px-2 py-1 rounded-md bg-card ml-auto text-focus"
                >
                  {metadata?.true_value}
                </Badge>
              </div>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-1">Confidence</p>
              <p className="text-lg font-semibold">
                {result.confidence ? `${Math.round(result.confidence * 100)}%` : 'N/A'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 
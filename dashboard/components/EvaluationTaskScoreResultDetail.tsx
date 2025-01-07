import React from 'react'
import { X, Microscope } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import { LabelBadgeComparison } from '@/components/LabelBadgeComparison'

interface EvaluationTaskScoreResultDetailProps {
  result: {
    id: string
    value: string
    confidence: number | null
    explanation: string | null
    metadata: {
      human_label: string | null
      correct: boolean
      human_explanation?: string | null
      text?: string | null
    }
    itemId: string | null
  }
  onClose: () => void
  navigationControls?: React.ReactNode
}

export function EvaluationTaskScoreResultDetail({ 
  result, 
  onClose, 
  navigationControls 
}: EvaluationTaskScoreResultDetailProps) {
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
        <div className="bg-card-light rounded-lg p-4 mt-1 h-[calc(100%-2rem)] overflow-y-auto">
          <div className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-1">
                <p className="text-sm text-muted-foreground">Value</p>
                <span className="text-sm text-muted-foreground">
                  ID: {result.itemId}
                </span>
              </div>
              <LabelBadgeComparison
                predictedLabel={result.value}
                actualLabel={result.metadata.human_label ?? ''}
                isCorrect={result.metadata.correct}
                isDetail={true}
              />
            </div>

            {result.explanation && (
              <div>
                <p className="text-sm text-muted-foreground mb-1">Explanation</p>
                <p className="text-sm whitespace-pre-wrap">
                  {result.explanation}
                </p>
              </div>
            )}

            {!result.metadata.correct && result.metadata.human_explanation && (
              <div>
                <p className="text-sm text-muted-foreground mb-1">Label comment</p>
                <p className="text-sm whitespace-pre-wrap">
                  {result.metadata.human_explanation}
                </p>
              </div>
            )}

            {result.confidence && (
              <div>
                <p className="text-sm text-muted-foreground mb-1">Confidence</p>
                <p className="text-lg font-semibold">
                  {Math.round(result.confidence * 100)}%
                </p>
              </div>
            )}

            {result.metadata.text && (
              <div>
                <p className="text-sm text-muted-foreground mb-1">Text</p>
                <p className="text-sm whitespace-pre-wrap font-mono">
                  {result.metadata.text}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
} 
import React from 'react'
import { X, Microscope } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import { LabelBadgeComparison } from '@/components/LabelBadgeComparison'
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
  const parsedMetadata = typeof result.metadata === 'string' ? 
    JSON.parse(JSON.parse(result.metadata)) : result.metadata

  const firstResultKey = parsedMetadata?.results ? 
    Object.keys(parsedMetadata.results)[0] : null
  const scoreResult = firstResultKey ? 
    parsedMetadata.results[firstResultKey] : null

  const isCorrect = scoreResult?.metadata?.correct ?? false

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
                  ID: {parsedMetadata?.item_id}
                </span>
              </div>
              <LabelBadgeComparison
                predictedLabel={scoreResult?.value}
                actualLabel={scoreResult?.metadata?.human_label}
                isCorrect={isCorrect}
                isDetail={true}
              />
            </div>

            {scoreResult?.explanation && (
              <div>
                <p className="text-sm text-muted-foreground mb-1">Explanation</p>
                <p className="text-sm whitespace-pre-wrap">
                  {scoreResult.explanation}
                </p>
              </div>
            )}

            {!isCorrect && scoreResult?.metadata?.human_explanation && (
              <div>
                <p className="text-sm text-muted-foreground mb-1">Label comment</p>
                <p className="text-sm whitespace-pre-wrap">
                  {scoreResult.metadata.human_explanation}
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

            <div>
              <p className="text-sm text-muted-foreground mb-1">Text</p>
              <p className="text-sm whitespace-pre-wrap font-mono">
                {scoreResult?.metadata?.text}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 
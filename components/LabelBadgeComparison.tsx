import React from 'react'
import { Badge } from '@/components/ui/badge'
import { ArrowRight, CheckCircle, AlertTriangle } from 'lucide-react'

interface LabelBadgeComparisonProps {
  predictedLabel: string
  actualLabel: string
  isCorrect: boolean
  showStatus?: boolean
  className?: string
  isFocused?: boolean
  isDetail?: boolean
}

export function LabelBadgeComparison({
  predictedLabel,
  actualLabel,
  isCorrect,
  showStatus = true,
  className = '',
  isFocused = false,
  isDetail = false
}: LabelBadgeComparisonProps) {
  const textColor = (isFocused || isDetail) ? 'text-focus' : 'text-foreground'

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Badge 
        variant="secondary"
        className={`text-sm px-2 py-0.5 rounded-md ${textColor} ${
          isCorrect ? "bg-true" : "bg-false"
        }`}
      >
        {predictedLabel}
      </Badge>
      {!isCorrect && (
        <>
          <ArrowRight className="h-5 w-5 text-muted-foreground" />
          <Badge
            variant="secondary"
            className={`text-sm px-2 py-0.5 rounded-md bg-neutral ${textColor}`}
          >
            {actualLabel}
          </Badge>
        </>
      )}
      {showStatus && (
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
      )}
    </div>
  )
} 
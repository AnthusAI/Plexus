import * as React from 'react'
import { Card } from './card'
import { cn } from '@/lib/utils'

export interface ScoreData {
  id: string
  name: string
  key: string
  description: string
  type: string
  configuration: any
  order: number
}

interface ScoreCardProps extends React.HTMLAttributes<HTMLDivElement> {
  score: ScoreData
  variant?: 'grid' | 'detail'
  isSelected?: boolean
  onClick?: () => void
}

export function ScoreCard({
  score,
  variant = 'grid',
  isSelected,
  onClick,
  className,
  ...props
}: ScoreCardProps) {
  return (
    <Card
      className={cn(
        "w-full",
        isSelected && "ring-2 ring-primary",
        className
      )}
      onClick={onClick}
      {...props}
    >
      <div className="p-4">
        <div className="space-y-2">
          <div className="text-sm">
            <div className="font-medium">{score.name}</div>
            <div className="text-muted-foreground">{score.description}</div>
          </div>
          <div className="text-sm text-muted-foreground">
            <div>Type: {score.type}</div>
            <div>Key: {score.key}</div>
          </div>
        </div>
      </div>
    </Card>
  )
} 
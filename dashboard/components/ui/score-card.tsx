import * as React from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { MoreHorizontal, X, Square, RectangleVertical } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'

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
  onClose?: () => void
  onToggleFullWidth?: () => void
  isFullWidth?: boolean
}

export function ScoreCard({
  score,
  variant = 'grid',
  isSelected,
  onClick,
  onClose,
  onToggleFullWidth,
  isFullWidth,
  className,
  ...props
}: ScoreCardProps) {
  if (variant === 'detail') {
    return (
      <Card
        className={cn(
          "w-full h-full flex flex-col overflow-hidden border-0",
          className
        )}
        {...props}
      >
        <div className="p-4 flex-1 flex flex-col min-h-0 w-full">
          <div className="flex justify-between items-start mb-6">
            <div className="space-y-2 flex-1">
              <h3 className="text-lg font-semibold">{score.name}</h3>
              <p className="text-sm text-muted-foreground">{score.description}</p>
              <div className="text-sm">
                <div><span className="font-medium">Key:</span> {score.key}</div>
                <div><span className="font-medium">Type:</span> {score.type}</div>
              </div>
            </div>
            <div className="flex gap-2">
              <CardButton
                icon={isFullWidth ? RectangleVertical : Square}
                onClick={() => onToggleFullWidth?.()}
                aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
              />
              <CardButton
                icon={X}
                onClick={() => onClose?.()}
                aria-label="Close"
              />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto w-full">
            <pre className="p-4 bg-background rounded-lg overflow-x-auto whitespace-pre-wrap break-words w-full max-w-full">
              <code className="block w-full overflow-x-auto">
                {/* Temporarily hidden for debugging */}
                {/* {JSON.stringify(score.configuration, null, 2)} */}
                [Configuration display temporarily hidden for debugging]
              </code>
            </pre>
          </div>
        </div>
      </Card>
    )
  }

  return (
    <Card
      className={cn(
        "w-full cursor-pointer hover:bg-accent/50 transition-colors",
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
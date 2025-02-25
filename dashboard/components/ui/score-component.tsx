import * as React from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { MoreHorizontal, X, Square, RectangleVertical, Save, X as Cancel } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Button } from '@/components/ui/button'

export interface ScoreData {
  id: string
  name: string
  key: string
  description: string
  type: string
  order: number
  icon?: React.ReactNode
}

interface ScoreComponentProps extends React.HTMLAttributes<HTMLDivElement> {
  score: ScoreData
  variant?: 'grid' | 'detail'
  isSelected?: boolean
  onClick?: () => void
  onClose?: () => void
  onToggleFullWidth?: () => void
  isFullWidth?: boolean
}

export function ScoreComponent({
  score,
  variant = 'grid',
  isSelected,
  onClick,
  onClose,
  onToggleFullWidth,
  isFullWidth,
  className,
  ...props
}: ScoreComponentProps) {
  return (
    <Card
      className={cn(
        "w-full cursor-pointer hover:bg-accent/50 transition-colors border-0",
        isSelected ? "bg-card-selected" : "bg-card",
        className
      )}
      onClick={onClick}
      {...props}
    >
      <div className="p-4">
        <div className="flex justify-between items-start">
          <div className="space-y-2">
            <div className="font-medium">{score.name}</div>
            <div className="text-sm text-muted-foreground">{score.type}</div>
            <div className="text-sm">{score.description}</div>
          </div>
          {score.icon && (
            <div className="text-muted-foreground">
              {score.icon}
            </div>
          )}
        </div>
      </div>
    </Card>
  )
} 
import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, Pencil, Database, ListTodo, X, Square, RectangleVertical } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'

export interface ScorecardData {
  id: string
  name: string
  key: string
  description: string
  type: string
  configuration: any
  order: number
  externalId?: string
  scoreCount?: number
}

interface ScorecardCardProps extends React.HTMLAttributes<HTMLDivElement> {
  score: ScorecardData
  onEdit?: () => void
  onViewData?: () => void
  isSelected?: boolean
  onClick?: () => void
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  variant?: 'grid' | 'detail'
}

const GridContent = React.memo(({ 
  score,
  isSelected 
}: { 
  score: ScorecardData
  isSelected?: boolean
}) => {
  const scoreCount = score.scoreCount || 0
  const scoreText = scoreCount === 1 ? 'Score' : 'Scores'

  return (
    <div className="flex justify-between items-start w-full">
      <div className="space-y-1.5">
        <div className="font-medium">{score.name}</div>
        <div className="text-sm text-muted-foreground">ID: {score.externalId || '-'}</div>
        <div className="text-sm text-muted-foreground">{scoreCount} {scoreText}</div>
      </div>
      <div className="text-muted-foreground">
        <ListTodo className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
      </div>
    </div>
  )
})

const DetailContent = React.memo(({ 
  score,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  onEdit,
  onViewData
}: { 
  score: ScorecardData
  isFullWidth: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onEdit?: () => void
  onViewData?: () => void
}) => {
  return (
    <div className="space-y-4 px-1">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-lg font-semibold">{score.name}</h3>
          <p className="text-sm text-muted-foreground">{score.description}</p>
        </div>
        <div className="flex gap-2">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <CardButton
                icon={MoreHorizontal}
                onClick={() => {}}
                aria-label="More options"
              />
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content align="end" className="min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
                {onEdit && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={onEdit}
                  >
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenu.Item>
                )}
                {onViewData && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={onViewData}
                  >
                    <Database className="mr-2 h-4 w-4" />
                    View Data
                  </DropdownMenu.Item>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          {onToggleFullWidth && (
            <CardButton
              icon={isFullWidth ? RectangleVertical : Square}
              onClick={onToggleFullWidth}
              aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
            />
          )}
          {onClose && (
            <CardButton
              icon={X}
              onClick={onClose}
              aria-label="Close"
            />
          )}
        </div>
      </div>
      
      <div className="space-y-2">
        <div className="text-sm">
          <div><span className="font-medium">Key:</span> {score.key}</div>
          <div><span className="font-medium">Type:</span> {score.type}</div>
        </div>
      </div>
    </div>
  )
})

export default function ScorecardCard({ 
  score, 
  onEdit, 
  onViewData, 
  variant = 'grid', 
  isSelected,
  onClick,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  className, 
  ...props 
}: ScorecardCardProps) {
  return (
    <div
      className={cn(
        "w-full rounded-lg bg-card text-card-foreground hover:bg-accent/50 transition-colors",
        isSelected && "bg-accent",
        className
      )}
      {...props}
    >
      <div className="flex justify-between items-start p-4">
        <div 
          className={cn(
            "flex-1",
            variant === 'grid' && "cursor-pointer"
          )}
          onClick={variant === 'grid' ? onClick : undefined}
          role={variant === 'grid' ? "button" : undefined}
          tabIndex={variant === 'grid' ? 0 : undefined}
          onKeyDown={variant === 'grid' ? (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onClick?.()
            }
          } : undefined}
        >
          {variant === 'grid' ? (
            <GridContent score={score} isSelected={isSelected} />
          ) : (
            <DetailContent 
              score={score} 
              isFullWidth={isFullWidth || false}
              onToggleFullWidth={onToggleFullWidth}
              onClose={onClose}
              onEdit={onEdit}
              onViewData={onViewData}
            />
          )}
        </div>
      </div>
    </div>
  )
} 
import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, X, Square, RectangleVertical, AudioLines, Info } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { Badge } from '@/components/ui/badge'
import { formatTimeAgo } from '@/utils/format-time'

export interface ItemData {
  id: number | string
  scorecard: string
  score: number
  date: string
  status: string
  results: number
  inferences: number
  cost: string
  icon?: React.ReactNode
}

interface ItemCardProps extends React.HTMLAttributes<HTMLDivElement> {
  item: ItemData
  onEdit?: () => void
  onViewData?: () => void
  isSelected?: boolean
  onClick?: () => void
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  variant?: 'grid' | 'detail'
  getBadgeVariant: (status: string) => string
}

const GridContent = React.memo(({ 
  item,
  getBadgeVariant,
  isSelected 
}: { 
  item: ItemData
  getBadgeVariant: (status: string) => string
  isSelected?: boolean
}) => {
  return (
    <div className="flex justify-between items-start w-full">
      <div className="space-y-1 max-w-[70%]">
        <div className="font-medium text-sm truncate" title={item.scorecard}>{item.scorecard}</div>
        <div className="text-xs text-muted-foreground">{formatTimeAgo(item.date)}</div>
      </div>
      <div className="flex flex-col items-end space-y-1">
        <div className="text-muted-foreground">
          {item.icon || <AudioLines className="h-[1.75rem] w-[1.75rem]" strokeWidth={1.25} />}
        </div>
        <Badge 
          className={`${getBadgeVariant(item.status)} text-xs px-2 py-0 h-5`}
        >
          {item.status}
        </Badge>
      </div>
    </div>
  )
})

interface DetailContentProps {
  item: ItemData
  getBadgeVariant: (status: string) => string
  isFullWidth: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onEdit?: () => void
  onViewData?: () => void
}

const DetailContent = React.memo(({ 
  item,
  getBadgeVariant,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  onEdit,
  onViewData,
}: DetailContentProps) => {
  return (
    <div className="w-full flex flex-col min-h-0">
      <div className="flex justify-between items-start w-full">
        <div className="space-y-2 flex-1">
          <h2 className="text-xl font-semibold">{item.scorecard}</h2>
          <p className="text-sm text-muted-foreground">
            {formatTimeAgo(item.date)}
          </p>
        </div>
        <div className="flex gap-2 ml-4">
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
                {onViewData && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={onViewData}
                  >
                    <Info className="mr-2 h-4 w-4" />
                    View Details
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

      <div className="grid grid-cols-2 gap-4 mt-4">
        <div>
          <p className="text-sm font-medium">Inferences</p>
          <p>{item.inferences}</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-medium">Status</p>
          <Badge 
            className={`w-24 justify-center ${getBadgeVariant(item.status)}`}
          >
            {item.status}
          </Badge>
        </div>
        <div>
          <p className="text-sm font-medium">Results</p>
          <p>{item.results}</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-medium">Cost</p>
          <p>{item.cost}</p>
        </div>
      </div>
    </div>
  )
})

export default function ItemCard({ 
  item, 
  onEdit, 
  onViewData, 
  variant = 'grid', 
  isSelected,
  onClick,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  getBadgeVariant,
  className, 
  ...props 
}: ItemCardProps) {
  return (
    <div
      className={cn(
        "w-full rounded-lg text-card-foreground hover:bg-accent/50 transition-colors",
        variant === 'grid' ? (
          isSelected ? "bg-card-selected" : "bg-card"
        ) : "bg-card-selected",
        variant === 'detail' && "h-full flex flex-col",
        className
      )}
      {...props}
    >
      <div className={cn(
        variant === 'grid' ? "p-3" : "p-4",
        "w-full",
        variant === 'detail' && "flex-1 flex flex-col min-h-0"
      )}>
        <div 
          className={cn(
            "w-full",
            variant === 'grid' && "cursor-pointer",
            variant === 'detail' && "h-full flex flex-col min-h-0"
          )}
          onClick={() => variant === 'grid' && onClick?.()}
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
            <GridContent item={item} getBadgeVariant={getBadgeVariant} isSelected={isSelected} />
          ) : (
            <DetailContent 
              item={item}
              getBadgeVariant={getBadgeVariant}
              isFullWidth={isFullWidth}
              onToggleFullWidth={onToggleFullWidth}
              onClose={onClose}
              onViewData={onViewData}
            />
          )}
        </div>
      </div>
    </div>
  )
} 
import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, X, Square, Columns2, AudioLines, Info } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { Badge } from '@/components/ui/badge'
import { Timestamp } from '@/components/ui/timestamp'
import { motion } from 'framer-motion'

export interface ItemData {
  id: number | string
  scorecard?: string
  score?: string | number | null
  date?: string
  status?: string
  results?: number
  inferences?: number
  cost?: string
  icon?: React.ReactNode
  
  // New fields from the Amplify model
  externalId?: string
  description?: string
  accountId?: string
  scorecardId?: string
  scoreId?: string
  evaluationId?: string
  updatedAt?: string
  createdAt?: string
  isEvaluation?: boolean
  isNew?: boolean
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
        <div className="font-medium text-sm truncate" title={item.scorecard}>{item.scorecard || 'Untitled Item'}</div>
        {item.score && (
          <div className="text-xs text-muted-foreground truncate" title={`Score: ${item.score}`}>
            {item.score}
          </div>
        )}
        {item.externalId && (
          <div className="text-xs text-muted-foreground truncate" title={`ID: ${item.externalId}`}>
            {item.externalId}
          </div>
        )}
        {item.date ? (
          <Timestamp 
            time={item.date} 
            variant="relative" 
            showIcon={false} 
            className="text-xs"
          />
        ) : (
          <div className="text-xs text-muted-foreground">No date</div>
        )}
      </div>
      <div className="flex flex-col items-end space-y-1">
        {item.icon || <AudioLines className="h-[1.75rem] w-[1.75rem]" strokeWidth={1.25} />}
        {item.status && (
          <Badge 
            className={`${getBadgeVariant(item.status)} text-xs px-2 py-0 h-5`}
            variant="outline"
          >
            {item.status}
          </Badge>
        )}
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
          <h2 className="text-xl font-semibold">{item.scorecard || 'Untitled Item'}</h2>
          {item.date ? (
            <Timestamp 
              time={item.date} 
              variant="relative" 
              className="text-sm"
            />
          ) : (
            <p className="text-sm text-muted-foreground">No date</p>
          )}
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
              icon={isFullWidth ? Columns2 : Square}
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
          <p>{item.inferences || 0}</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-medium">Status</p>
          <Badge 
            className={`w-24 justify-center ${item.status ? getBadgeVariant(item.status) : ''}`}
            variant="outline"
          >
            {item.status || 'Unknown'}
          </Badge>
        </div>
        <div>
          <p className="text-sm font-medium">Results</p>
          <p>{item.results || 0}</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-medium">Cost</p>
          <p>{item.cost || '$0.000'}</p>
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
  // Extract HTML props that might conflict with motion props
  const { onDrag, ...htmlProps } = props as any;
  
  return (
    <motion.div
      initial={item.isNew ? { opacity: 0 } : { opacity: 1 }}
      animate={{ opacity: 1 }}
      transition={{ 
        duration: 1.0,
        ease: "easeOut"
      }}
      className={cn(
        "w-full rounded-lg text-card-foreground hover:bg-accent/50 relative",
        variant === 'grid' ? (
          isSelected ? "bg-card-selected" : "bg-card"
        ) : "bg-card-selected",
        variant === 'detail' && "h-full flex flex-col",
        className
      )}
      {...htmlProps}
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
              onEdit={onEdit}
            />
          )}
        </div>
      </div>
    </motion.div>
  )
} 
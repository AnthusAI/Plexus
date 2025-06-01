import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, X, Square, Columns2, StickyNote, Info, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { Badge } from '@/components/ui/badge'
import { Timestamp } from '@/components/ui/timestamp'
import { motion } from 'framer-motion'
import ItemScoreResultCard from './ItemScoreResultCard'
import { IdentifierDisplay } from '@/components/ui/identifier-display'
import NumberFlowWrapper from '@/components/ui/number-flow'

// Interface for scorecard results
interface ScorecardResult {
  scorecardId: string;
  scorecardName: string;
  resultCount: number;
}

// Interface for the new Identifier model structure
export interface IdentifierItem {
  name: string;
  value: string;
  url?: string;
  position?: number;
}

// Clean interface for ItemCard parameters
export interface ItemData {
  // Core required parameters
  id: number | string
  timestamp: string // ISO string for when the item was created/updated
  duration?: number // Duration in seconds (optional for elapsed time display)
  scorecards: ScorecardResult[] // List of scorecards with result counts
  
  // Optional UI fields
  icon?: React.ReactNode
  externalId?: string
  description?: string
  identifiers?: string | IdentifierItem[] // Support both JSON string (legacy) and new array format
  isNew?: boolean
  isLoadingResults?: boolean
  
  // Legacy fields for backwards compatibility (will be phased out)
  date?: string
  status?: string
  results?: number
  inferences?: number
  cost?: string
  accountId?: string
  scorecardId?: string
  scoreId?: string
  evaluationId?: string
  updatedAt?: string
  createdAt?: string
  isEvaluation?: boolean
  groupedScoreResults?: any
  scorecardBreakdown?: Array<{
    scorecardId: string;
    scorecardName: string;
    count: number;
  }>
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
  const totalResults = item.scorecards.reduce((sum, sc) => sum + sc.resultCount, 0);
  const hasMultipleScorecards = item.scorecards.length > 1;

  return (
    <div className="w-full relative">
      {/* Icon positioned absolutely in top-right */}
      <div className="absolute top-0 right-0 flex flex-col items-center space-y-1 z-10">
        {item.icon || <StickyNote className="h-[1.75rem] w-[1.75rem]" strokeWidth={1.25} />}
        <div className="text-xs text-muted-foreground text-center" title="Item">
          <span className="font-semibold">Item</span>
        </div>
      </div>
      
      {/* Invisible float element that creates space for icon/label but allows text to wrap under */}
      <div className="float-right w-16 h-12"></div>
      
      {/* Content that flows around and under the icon */}
      <div className="space-y-1">
        <IdentifierDisplay 
          externalId={item.externalId}
          identifiers={item.identifiers}
          iconSize="md"
          textSize="xs"
        />

        <Timestamp 
          time={item.timestamp} 
          variant="relative" 
          showIcon={true} 
          className="text-xs"
        />

        {/* Elapsed time display between createdAt and updatedAt */}
        {item.createdAt && item.updatedAt && (
          <Timestamp 
            time={item.createdAt}
            completionTime={item.updatedAt}
            variant="elapsed" 
            showIcon={true}
            className="text-xs"
          />
        )}

        {/* Scorecard summary */}
        {item.scorecards.length > 0 && (
          <div className="font-semibold text-sm mt-3">
            {hasMultipleScorecards ? 
              `${item.scorecards.length} scorecards` : 
              item.scorecards[0]?.scorecardName || 'Scorecard'}
          </div>
        )}
        
        {/* Results count - fixed height to prevent layout jiggling */}
        <div className="flex flex-col gap-0.5 text-xs">
          {item.isLoadingResults ? (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading results...</span>
            </div>
          ) : item.scorecards.length > 0 ? (
            <div>
              <NumberFlowWrapper value={totalResults} /> result{totalResults !== 1 ? 's' : ''}
            </div>
          ) : (
            <div>
              <NumberFlowWrapper value={0} /> results
            </div>
          )}
        </div>
        
        {/* Clear the float */}
        <div className="clear-both"></div>
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
  const totalResults = item.scorecards.reduce((sum, sc) => sum + sc.resultCount, 0);
  const hasMultipleScorecards = item.scorecards.length > 1;

  return (
    <div className="w-full flex flex-col min-h-0">
      <div className="flex justify-between items-start w-full">
        <div className="space-y-2 flex-1">
          {/* Header with primary scorecard name */}
          <div className="text-xs text-muted-foreground">
            <span className="font-semibold">
              {hasMultipleScorecards ? 
                `${item.scorecards.length} Scorecards` : 
                (item.scorecards[0]?.scorecardName || 'Untitled Item')}
            </span>
          </div>

          <IdentifierDisplay 
            externalId={item.externalId}
            identifiers={item.identifiers}
            iconSize="md"
            textSize="xs"
          />

          <Timestamp 
            time={item.timestamp} 
            variant="relative" 
            showIcon={true}
            className="text-xs"
          />

          {/* Elapsed time display between createdAt and updatedAt */}
          {item.createdAt && item.updatedAt && (
            <Timestamp 
              time={item.createdAt}
              completionTime={item.updatedAt}
              variant="elapsed" 
              showIcon={true}
              className="text-xs"
            />
          )}
          
          {/* Results summary */}
          <div className="text-sm font-semibold">
            {totalResults} result{totalResults !== 1 ? 's' : ''}
          </div>
          
          {/* Loading state */}
          {item.isLoadingResults && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading results...</span>
            </div>
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
      
      {/* Scorecard details section - show when we have multiple scorecards */}
      {hasMultipleScorecards && (
        <div className="mt-2 overflow-auto">
          <div className="space-y-4 pb-2">
            {item.scorecards.map((scorecard) => (
              <ItemScoreResultCard
                key={scorecard.scorecardId}
                scorecardName={scorecard.scorecardName}
                scores={[]} // This would need to be populated with actual score data when available
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
})

const ItemCard = React.forwardRef<HTMLDivElement, ItemCardProps>(({ 
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
}, ref) => {
  // Extract HTML props that might conflict with motion props
  const { onDrag, ...htmlProps } = props as any;
  
  // Debug ref to inspect the actual DOM element
  const debugRef = React.useCallback((node: HTMLDivElement | null) => {
    if (node && item.isNew) {
      console.log('🔍 DOM ELEMENT DEBUG:', {
        id: item.id,
        isNew: item.isNew,
        element: node,
        className: node.className,
        computedStyle: window.getComputedStyle(node),
        backgroundColor: window.getComputedStyle(node).backgroundColor,
        border: window.getComputedStyle(node).border,
        boxShadow: window.getComputedStyle(node).boxShadow,
        transform: window.getComputedStyle(node).transform
      });
    }
    if (ref) {
      if (typeof ref === 'function') {
        ref(node);
      } else {
        ref.current = node;
      }
    }
  }, [item.isNew, item.id, ref]);

  // Debug logging for new items
  React.useEffect(() => {
    if (item.isNew) {
      console.log('🟣✨ NEW ITEM CARD WITH RED/YELLOW EFFECTS:', {
        id: item.id,
        externalId: item.externalId,
        isNew: item.isNew,
        variant: variant,
        shouldHaveClass: 'new-item-shadow',
        shouldHaveInlineStyles: 'red background, yellow border',
        timestamp: new Date().toISOString()
      });
    }
  }, [item.isNew, item.id, item.externalId, variant]);
  
  return (
    <motion.div
      ref={debugRef}
      initial={{ opacity: 1 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "w-full rounded-lg text-card-foreground hover:bg-accent/50 relative",
        variant === 'grid' ? (
          isSelected ? "bg-card-selected" : "bg-card"
        ) : "bg-card-selected",
        variant === 'detail' && "h-full flex flex-col",
        item.isNew && "new-item-shadow",
        ((variant === 'grid' && isSelected) || variant === 'detail') && "selected-border-rounded",
        className
      )}
      {...htmlProps}
    >

      <div className={cn(
        variant === 'grid' ? "p-3" : "p-4",
        "w-full relative z-10",
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
});

ItemCard.displayName = 'ItemCard';

export default ItemCard; 
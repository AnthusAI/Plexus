import * as React from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
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
import ItemScoreResults from '../ItemScoreResults'
import { useItemScoreResults } from '@/hooks/useItemScoreResults'

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
  text?: string // For detail view text display
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
  skeletonMode?: boolean
}

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
  skeletonMode = false,
  className, 
  ...props 
}, ref) => {
  const [isNarrowViewport, setIsNarrowViewport] = React.useState(false)
  
  // Use the score results hook for detail view
  const { groupedResults, isLoading, error } = useItemScoreResults(
    variant === 'detail' ? String(item.id) : null
  )

  // Extract HTML props that might conflict with motion props
  const { onDrag, ...htmlProps } = props as any;
  
  const totalResults = item.scorecards.reduce((sum, sc) => sum + sc.resultCount, 0);
  const hasMultipleScorecards = item.scorecards.length > 1;

  React.useEffect(() => {
    if (variant === 'detail') {
      const checkViewportWidth = () => {
        setIsNarrowViewport(window.innerWidth < 640)
      }

      checkViewportWidth()
      window.addEventListener('resize', checkViewportWidth)
      return () => window.removeEventListener('resize', checkViewportWidth)
    }
  }, [variant])

  // Grid mode skeleton content
  const renderGridSkeleton = () => (
    <div className="space-y-1">
      {/* Skeleton identifier display */}
      <div className="flex items-start gap-1">
        <div className="h-4 w-4 bg-muted rounded animate-pulse flex-shrink-0" />
        <div className="h-3 w-20 bg-muted rounded animate-pulse" />
      </div>

      {/* Skeleton timestamp */}
      <div className="flex items-start gap-1">
        <div className="h-4 w-4 bg-muted rounded animate-pulse flex-shrink-0" />
        <div className="h-3 w-16 bg-muted rounded animate-pulse" />
      </div>

      {/* Skeleton elapsed time */}
      <div className="flex items-start gap-1">
        <div className="h-4 w-4 bg-muted rounded animate-pulse flex-shrink-0" />
        <div className="h-3 w-12 bg-muted rounded animate-pulse" />
      </div>

      {/* Skeleton scorecard name */}
      <div className="h-4 w-24 bg-muted rounded animate-pulse mt-3" />
      
      {/* Skeleton results count */}
      <div className="h-3 w-16 bg-muted rounded animate-pulse" />
    </div>
  )

  // Grid mode content
  const renderGridContent = () => (
    <div className="space-y-1">
      <IdentifierDisplay 
        externalId={item.externalId}
        identifiers={item.identifiers}
        iconSize="md"
        textSize="xs"
        skeletonMode={skeletonMode}
      />

      <Timestamp 
        time={item.timestamp} 
        variant="relative" 
        showIcon={true} 
        className="text-xs"
        skeletonMode={skeletonMode}
      />

      {/* Elapsed time display between createdAt and updatedAt */}
      {item.createdAt && item.updatedAt && (
        <Timestamp 
          time={item.createdAt}
          completionTime={item.updatedAt}
          variant="elapsed" 
          showIcon={true}
          className="text-xs"
          skeletonMode={skeletonMode}
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
            <NumberFlowWrapper value={totalResults} skeletonMode={skeletonMode} /> result{totalResults !== 1 ? 's' : ''}
          </div>
        ) : (
          <div>
            <NumberFlowWrapper value={0} skeletonMode={skeletonMode} /> results
          </div>
        )}
      </div>
    </div>
  )

  // Grid mode layout
  if (variant === 'grid') {
    return (
      <motion.div
        ref={ref}
        initial={{ opacity: 1 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        className={cn(
          "w-full rounded-lg text-card-foreground hover:bg-accent/50 relative cursor-pointer",
          isSelected ? "bg-card-selected" : "bg-card",
          item.isNew && "new-item-shadow",
          isSelected && "selected-border-rounded",
          className
        )}
        onClick={onClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onClick?.()
          }
        }}
        {...htmlProps}
      >
        <div className="p-3 w-full relative z-10">
          <div className="w-full relative">
            {/* Top-right icon */}
            <div className="absolute top-0 right-0 z-10">
              <div className="flex flex-col items-center space-y-1">
                {item.icon || <StickyNote className="h-[1.75rem] w-[1.75rem]" strokeWidth={1.25} />}
                <div className="text-xs text-muted-foreground text-center" title="Item">
                  <span className="font-semibold">Item</span>
                </div>
              </div>
            </div>
            
            {/* Float spacer for icon */}
            <div className="float-right w-16 h-12"></div>
            
            {/* Content */}
            {skeletonMode ? renderGridSkeleton() : renderGridContent()}
            
            {/* Clear the float */}
            <div className="clear-both"></div>
          </div>
        </div>
      </motion.div>
    )
  }

  // Detail mode layout - simplified to fit within existing container
  return (
    <Card className="rounded-none sm:rounded-lg h-full flex flex-col bg-card border-none">
      <CardHeader className="flex-shrink-0 flex flex-row items-start justify-between py-4 px-4 sm:px-3 space-y-0">
        <div>
          <h2 className="text-xl text-muted-foreground font-semibold">Item Details</h2>
          <div className="mt-1 space-y-1">
            <IdentifierDisplay 
              externalId={item.externalId}
              identifiers={item.identifiers}
              iconSize="md"
              textSize="sm"
              skeletonMode={skeletonMode}
            />
            <div className="text-sm text-muted-foreground">
              <Timestamp time={item.timestamp || item.date || ''} variant="relative" className="text-xs" skeletonMode={skeletonMode} />
            </div>
            {item.createdAt && item.updatedAt && (
              <Timestamp time={item.createdAt} completionTime={item.updatedAt} variant="elapsed" className="text-xs" skeletonMode={skeletonMode} />
            )}
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <CardButton
                icon={MoreHorizontal}
                onClick={() => {}}
                aria-label="More options"
                skeletonMode={skeletonMode}
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
          {!isNarrowViewport && onToggleFullWidth && (
            <CardButton
              icon={isFullWidth ? Columns2 : Square}
              onClick={onToggleFullWidth}
              aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
              skeletonMode={skeletonMode}
            />
          )}
          {onClose && (
            <CardButton
              icon={X}
              onClick={onClose}
              aria-label="Close"
              skeletonMode={skeletonMode}
            />
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-grow overflow-auto px-4 sm:px-3 pb-4">
        <div className="space-y-4">
          {/* Text field display */}
          {item.text && (
            <div>
              <h3 className="text-sm font-medium text-foreground mb-2">Text</h3>
              <div className="rounded-lg bg-background p-3 border">
                <p className="text-sm whitespace-pre-wrap">{item.text}</p>
              </div>
            </div>
          )}
          
          <ItemScoreResults
            groupedResults={groupedResults}
            isLoading={isLoading}
            error={error}
            itemId={String(item.id)}
          />
        </div>
      </CardContent>
    </Card>
  )
});

ItemCard.displayName = 'ItemCard';

export default ItemCard; 
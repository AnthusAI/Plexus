import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, X, Square, Columns2, StickyNote, Info, ChevronDown, ChevronUp, Clock, IdCard, Loader2, ListTodo } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { Badge } from '@/components/ui/badge'
import { Timestamp } from '@/components/ui/timestamp'
import { motion } from 'framer-motion'
import ItemScoreResultCard from './ItemScoreResultCard'

// Interface for grouped score results
interface GroupedScoreResults {
  [scorecardId: string]: {
    scorecardName: string;
    scores: {
      scoreId: string;
      scoreName: string;
    }[];
  }
}

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
  
  // New field for grouped score results
  groupedScoreResults?: GroupedScoreResults
  
  // Score result loading state
  isLoadingResults?: boolean
  
  // Score result breakdown by scorecard
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
  // Add debugging for the score property
  React.useEffect(() => {
    console.log(`ItemCard rendering with score: ${item.score}`, item);
    console.log('GroupedScoreResults:', item.groupedScoreResults);
  }, [item]);
  
  // Get scores to display 
  const getScoreDisplays = () => {
    // If we have groupedScoreResults, use those
    if (item.groupedScoreResults && Object.keys(item.groupedScoreResults).length > 0) {
      const displays: { scorecard: string, scores: string[] }[] = [];
      
      Object.values(item.groupedScoreResults).forEach(data => {
        displays.push({
          scorecard: data.scorecardName,
          scores: data.scores.map(s => s.scoreName)
        });
      });
      
      return displays;
    } else if (item.scorecard) {
      // Fall back to old single score if available
      return [{
        scorecard: item.scorecard,
        scores: item.score ? [item.score.toString()] : []
      }];
    } else if (item.isEvaluation) {
      return [{
        scorecard: 'Evaluation',
        scores: ["Evaluation"]
      }];
    } else {
      return [{
        scorecard: 'Item',
        scores: []
      }];
    }
  };
  
  const scoreDisplays = getScoreDisplays();
  const hasMultipleScores = scoreDisplays.reduce((total, display) => total + display.scores.length, 0) > 1;
  const hasMultipleScorecards = scoreDisplays.length > 1;
  
  // Determine what to show when collapsed
  const primaryScorecard = scoreDisplays[0]?.scorecard || 'Untitled Item';
  const primaryScore = scoreDisplays[0]?.scores[0] || '';
  
  // Get total score count
  const totalScores = scoreDisplays.reduce((total, display) => total + display.scores.length, 0);

  return (
    <div className="flex justify-between items-start w-full">
      <div className="space-y-1 max-w-[70%]">
        {/* Header order: 1. Scorecard name */}
        <div className="font-semibold text-sm truncate" title={primaryScorecard}>
          {primaryScorecard}
        </div>
        
        {/* Header order: 2. Timestamp */}
        {item.date ? (
          <Timestamp 
            time={item.date} 
            variant="relative" 
            showIcon={true} 
            className="text-xs"
          />
        ) : (
          <div className="text-xs text-muted-foreground">No date</div>
        )}
        
        {/* Header order: 3. External ID (if available) */}
        {item.externalId && (
          <div className="text-xs text-muted-foreground truncate flex items-center gap-1" title={`ID: ${item.externalId}`}>
            <IdCard className="h-3 w-3" />
            <span>{item.externalId}</span>
          </div>
        )}
        
        {/* Header order: 4. Score name or count */}
        {(hasMultipleScores || primaryScore) && (
          <div className="font-semibold text-sm truncate" title={hasMultipleScores ? `${totalScores} scores` : `Score: ${primaryScore}`}>
            {hasMultipleScores ? 
              `${totalScores} ${totalScores === 1 ? 'score' : 'scores'}` : 
              primaryScore}
          </div>
        )}
        
        {/* Score results count with loading state */}
        <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
          {item.isLoadingResults ? (
            <div className="flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>Loading results...</span>
            </div>
          ) : item.scorecardBreakdown && item.scorecardBreakdown.length > 0 ? (
            item.scorecardBreakdown.map((breakdown, index) => (
              <div key={breakdown.scorecardId || index} className="flex flex-col">
                <div className="font-medium text-xs flex items-center gap-1">
                  <ListTodo className="h-3 w-3" />
                  <span>{breakdown.scorecardName}</span>
                </div>
                <div>{breakdown.count} result{breakdown.count !== 1 ? 's' : ''}</div>
              </div>
            ))
          ) : (
            <span>{item.results || 0} result{(item.results || 0) !== 1 ? 's' : ''}</span>
          )}
        </div>
      </div>
      <div className="flex flex-col items-end space-y-1">
        {item.icon || <StickyNote className="h-[1.75rem] w-[1.75rem]" strokeWidth={1.25} />}
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
  // Function to get all scorecard and score information
  const getScoreInfo = () => {
    if (item.groupedScoreResults && Object.keys(item.groupedScoreResults).length > 0) {
      return Object.values(item.groupedScoreResults).map(data => ({
        scorecardName: data.scorecardName,
        scores: data.scores.map(s => ({
          scoreName: s.scoreName,
          createdAt: item.createdAt
        }))
      }));
    } else if (item.scorecard) {
      return [{
        scorecardName: item.scorecard,
        scores: item.score ? [{
          scoreName: item.score.toString(),
          createdAt: item.createdAt
        }] : []
      }];
    } else if (item.isEvaluation) {
      return [{
        scorecardName: 'Evaluation',
        scores: [{
          scoreName: "Evaluation",
          createdAt: item.createdAt
        }]
      }];
    } else {
      return [{
        scorecardName: 'Item',
        scores: []
      }];
    }
  };
  
  const scoreInfo = getScoreInfo();
  
  // Log the score info for debugging
  React.useEffect(() => {
    console.log('DetailContent scoreInfo:', scoreInfo);
    console.log('GroupedScoreResults:', item.groupedScoreResults);
  }, [item, scoreInfo]);

  // Get a single display name for the primary score (for the basic info section)
  const getPrimaryScoreDisplay = () => {
    if (scoreInfo.length === 0) return "";
    if (scoreInfo[0].scores.length === 0) return "";
    
    // If we have one scorecard with one score, just show that
    if (scoreInfo.length === 1 && scoreInfo[0].scores.length === 1) {
      return scoreInfo[0].scores[0].scoreName;
    }
    
    // Otherwise, show count
    const totalScores = scoreInfo.reduce((total, info) => total + info.scores.length, 0);
    return `${totalScores} scores in ${scoreInfo.length} scorecard${scoreInfo.length > 1 ? 's' : ''}`;
  };
  
  // Check if we have multiple scores
  const hasMultipleScores = scoreInfo.reduce((total, info) => total + info.scores.length, 0) > 1;
  
  // Get total score count
  const totalScores = scoreInfo.reduce((total, info) => total + info.scores.length, 0);
  
  // Get primary score
  const primaryScore = scoreInfo[0]?.scores[0]?.scoreName || '';

  return (
    <div className="w-full flex flex-col min-h-0">
      <div className="flex justify-between items-start w-full">
        <div className="space-y-2 flex-1">
          {/* Header order: 1. Scorecard name - reduced text size to match grid view */}
          <h2 className="text-sm font-semibold truncate">{scoreInfo[0]?.scorecardName || 'Untitled Item'}</h2>
          
          {/* Header order: 2. Timestamp - reduced text size to match grid view */}
          {item.date ? (
            <Timestamp 
              time={item.date} 
              variant="relative" 
              className="text-xs"
            />
          ) : (
            <p className="text-xs text-muted-foreground">No date</p>
          )}
          
          {/* Header order: 3. External ID (if available) - reduced text size to match grid view */}
          {item.externalId && (
            <div className="text-xs text-muted-foreground truncate flex items-center gap-1" title={`ID: ${item.externalId}`}>
              <IdCard className="h-3 w-3" />
              <span>{item.externalId}</span>
            </div>
          )}
          
          {/* Header order: 4. Score name or count - reduced text size to match grid view */}
          {(hasMultipleScores || primaryScore) && (
            <div className="text-sm font-semibold truncate" title={hasMultipleScores ? `${totalScores} scores` : `Score: ${primaryScore}`}>
              {hasMultipleScores ? 
                `${totalScores} ${totalScores === 1 ? 'score' : 'scores'}` : 
                primaryScore}
            </div>
          )}
          
          {/* Score results count with loading state */}
          <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
            {item.isLoadingResults ? (
              <div className="flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Loading results...</span>
              </div>
            ) : item.scorecardBreakdown && item.scorecardBreakdown.length > 0 ? (
              item.scorecardBreakdown.map((breakdown, index) => (
                <div key={breakdown.scorecardId || index} className="flex flex-col">
                  <div className="font-medium text-xs flex items-center gap-1">
                    <ListTodo className="h-3 w-3" />
                    <span>{breakdown.scorecardName}</span>
                  </div>
                  <div>{breakdown.count} result{breakdown.count !== 1 ? 's' : ''}</div>
                </div>
              ))
            ) : (
              <span>{item.results || 0} result{(item.results || 0) !== 1 ? 's' : ''}</span>
            )}
          </div>
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
      
      {/* Score results section - "Score Results" header removed */}
      {scoreInfo.length > 0 && (scoreInfo.length > 1 || scoreInfo[0].scores.length > 1) && (
        <div className="mt-2 overflow-auto">
          <div className="space-y-4 pb-2">
            {scoreInfo.map((info, i) => (
              <ItemScoreResultCard
                key={i}
                scorecardName={info.scorecardName}
                scores={info.scores}
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
  
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 1 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
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
});

ItemCard.displayName = 'ItemCard';

export default ItemCard; 
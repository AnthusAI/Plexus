import * as React from 'react'
import { cn } from '@/lib/utils'
import { Timestamp } from '@/components/ui/timestamp'

interface ScoreInfo {
  scoreName: string;
  createdAt?: string;
}

interface ItemScoreResultCardProps {
  scorecardName: string;
  scores: ScoreInfo[];
  className?: string;
}

/**
 * A card component for displaying score results grouped by scorecard
 */
export const ItemScoreResultCard = React.forwardRef<
  HTMLDivElement,
  ItemScoreResultCardProps
>(({ scorecardName, scores, className }, ref) => {
  return (
    <div className="w-full" ref={ref}>
      {/* Outer container with background color - no border */}
      <div className="bg-background rounded-lg p-3">
        {/* Scorecard name header - changed from card to normal text header */}
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold">{scorecardName}</h4>
          <span className="text-xs text-muted-foreground">
            {scores.length} {scores.length === 1 ? 'score' : 'scores'}
          </span>
        </div>
        
        {/* Score results - completely flat with no borders or shadows */}
        <div className="space-y-2">
          {scores.map((score, index) => (
            <div 
              key={index} 
              className={cn(
                "w-full bg-card rounded-md hover:bg-accent/10 transition-colors duration-200",
                className
              )}
            >
              <div className="p-3 flex items-center justify-between">
                <div className="text-sm font-medium">{score.scoreName}</div>
                {score.createdAt && (
                  <Timestamp
                    time={score.createdAt}
                    variant="relative"
                    showIcon={false}
                    className="text-xs text-muted-foreground"
                  />
                )}
              </div>
            </div>
          ))}
          
          {scores.length === 0 && (
            <div className="text-sm text-muted-foreground italic px-3 py-2">
              No scores available
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

ItemScoreResultCard.displayName = "ItemScoreResultCard";

export default ItemScoreResultCard; 
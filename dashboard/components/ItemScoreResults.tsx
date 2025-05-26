import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Timestamp } from '@/components/ui/timestamp';
import Link from 'next/link';
import { GroupedScoreResults, ScoreResultWithDetails } from '@/hooks/useItemScoreResults';

interface ItemScoreResultsProps {
  groupedResults: GroupedScoreResults;
  isLoading: boolean;
  error: string | null;
  itemId: string;
}

// Skeleton components for loading state
const ScoreResultSkeleton = () => (
  <div className="mb-3 bg-background rounded-lg p-4">
    <div className="flex items-start justify-between">
      <div className="flex-1">
        <div className="h-4 bg-muted rounded w-32 mb-2 animate-pulse"></div>
        <div className="h-3 bg-muted rounded w-20 mb-2 animate-pulse"></div>
      </div>
      <div className="flex flex-col items-end gap-1">
        <div className="h-6 bg-muted rounded w-12 animate-pulse"></div>
        <div className="h-3 bg-muted rounded w-16 animate-pulse"></div>
      </div>
    </div>
    <div className="mt-3">
      <div className="h-3 bg-muted rounded w-16 mb-2 animate-pulse"></div>
      <div className="h-3 bg-muted rounded w-full mb-1 animate-pulse"></div>
      <div className="h-3 bg-muted rounded w-3/4 animate-pulse"></div>
    </div>
  </div>
);

const ScoreResultsSkeletonLoader = () => (
  <div className="space-y-4">
    <div className="flex items-center justify-between">
      <div className="h-6 bg-muted rounded w-32 animate-pulse"></div>
      <div className="h-6 bg-muted rounded w-24 animate-pulse"></div>
    </div>
    <div className="space-y-3">
      {[...Array(6)].map((_, i) => (
        <ScoreResultSkeleton key={i} />
      ))}
    </div>
  </div>
);

const ScoreResultCard: React.FC<{ result: ScoreResultWithDetails }> = ({ result }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Check if explanation is long enough to need expansion
  const needsExpansion = result.explanation && result.explanation.length > 200;
  const displayExplanation = needsExpansion && !isExpanded 
    ? result.explanation!.substring(0, 200) + '...' 
    : result.explanation;
  return (
    <div className="mb-3 bg-background rounded-lg p-4 relative overflow-visible">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-sm font-semibold">{result.score?.name || 'Unknown Score'}</h4>
          </div>
          <div className="text-xs text-muted-foreground mb-2">
            <Timestamp time={result.updatedAt || result.createdAt} variant="relative" />
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant="secondary">
            {result.value}
          </Badge>
          {result.confidence !== null && (
            <span className="text-xs text-muted-foreground">
              {Math.round((result.confidence || 0) * 100)}% confidence
            </span>
          )}
        </div>
      </div>
      {result.explanation && (
        <div className="mt-3 text-sm text-muted-foreground">
          <strong>Explanation:</strong>
          <p className="mt-1">{displayExplanation}</p>
          {needsExpansion && (
            <div className="flex justify-center">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1 h-auto -mb-2 relative z-10"
              >
                {isExpanded ? (
                  <ChevronUp className="h-3 w-3" />
                ) : (
                  <ChevronDown className="h-3 w-3" />
                )}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const ItemScoreResults: React.FC<ItemScoreResultsProps> = ({
  groupedResults,
  isLoading,
  error,
  itemId
}) => {
  if (isLoading) {
    return <ScoreResultsSkeletonLoader />;
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="text-center text-red-600">
            <p>Error loading score results: {error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const scorecardIds = Object.keys(groupedResults);
  
  if (scorecardIds.length === 0) {
    return (
      <div className="py-8">
        <div className="text-center text-muted-foreground">
          <p>No score results found for this item.</p>
          <p className="text-xs mt-1">Score results will appear here once the item has been processed.</p>
        </div>
      </div>
    );
  }

  const totalResults = scorecardIds.reduce((sum, id) => sum + groupedResults[id].scores.length, 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Score Results</h3>
        <Badge variant="secondary">
          {totalResults} result{totalResults !== 1 ? 's' : ''} across {scorecardIds.length} scorecard{scorecardIds.length !== 1 ? 's' : ''}
        </Badge>
      </div>

      <Accordion type="multiple" defaultValue={scorecardIds} className="w-full">
        {scorecardIds.map((scorecardId) => {
          const group = groupedResults[scorecardId];
          return (
            <AccordionItem key={scorecardId} value={scorecardId}>
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center justify-between w-full pr-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{group.scorecardName}</span>
                  </div>
                  <Badge variant="outline">
                    {group.scores.length} score{group.scores.length !== 1 ? 's' : ''}
                  </Badge>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="pt-2">
                  <div className="space-y-3">
                    {group.scores.map((result) => (
                      <ScoreResultCard key={result.id} result={result} />
                    ))}
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          );
        })}
      </Accordion>
    </div>
  );
};

export default ItemScoreResults;
import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, ExternalLink, ChevronDown, ChevronUp, ListChecks, IdCard, Box } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

import { Timestamp } from '@/components/ui/timestamp';
import Link from 'next/link';
import { GroupedScoreResults, ScoreResultWithDetails } from '@/hooks/useItemScoreResults';
import { IdentifierDisplay } from '@/components/ui/identifier-display';
import NumberFlowWrapper from '@/components/ui/number-flow';
import { useTranslations } from '@/app/contexts/TranslationContext';

interface ItemScoreResultsProps {
  groupedResults: GroupedScoreResults;
  isLoading: boolean;
  error: string | null;
  itemId: string;
  onScoreResultSelect?: (scoreResult: ScoreResultWithDetails) => void;
  selectedScoreResultId?: string;
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

const ScoreResultCard: React.FC<{ 
  result: ScoreResultWithDetails;
  onClick?: () => void;
  isSelected?: boolean;
}> = ({ result, onClick, isSelected }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Check if explanation is long enough to need expansion
  const needsExpansion = result.explanation && result.explanation.length > 200;
  const displayExplanation = needsExpansion && !isExpanded 
    ? result.explanation!.substring(0, 200) + '...' 
    : result.explanation;
  
  return (
    <motion.div
      initial={{ opacity: result.isNew ? 0 : 1 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={`mb-3 bg-background rounded-lg p-4 relative overflow-visible cursor-pointer hover:bg-accent/50 transition-colors ${
        result.isNew ? 'new-item-shadow' : ''
      } ${
        isSelected ? 'bg-card-selected selected-border-rounded' : ''
      }`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick?.()
        }
      }}
    >
      <div className="flex items-start justify-between relative z-10">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-sm font-semibold">{result.score?.name || 'Unknown Score'}</h4>
          </div>
          <div className="text-xs text-muted-foreground mb-2">
            {result.score?.externalId && (
              <div className="mb-1">
                <IdentifierDisplay 
                  externalId={result.score.externalId}
                  iconSize="md"
                  textSize="xs"
                  displayMode="full"
                />
              </div>
            )}
            <Timestamp time={result.updatedAt || result.createdAt || new Date().toISOString()} variant="relative" className="text-xs" />
            {result.createdAt && result.updatedAt && (
              <div className="mt-0.5">
                <Timestamp time={result.createdAt} completionTime={result.updatedAt} variant="elapsed" className="text-xs" />
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant="secondary">
            {result.value}
          </Badge>
          {result.confidence !== null && (
            <span className="text-xs text-muted-foreground">
              {Math.round((result.confidence || 0) * 100)}% {t('confidence')}
            </span>
          )}
        </div>
      </div>
      {result.explanation && (
        <div className="mt-3 text-sm text-muted-foreground relative z-10">
          <div className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-muted-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              components={{
                // Customize components for better styling
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                ul: ({ children }) => <ul className="mb-2 ml-4 list-disc">{children}</ul>,
                ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal">{children}</ol>,
                li: ({ children }) => <li className="mb-1">{children}</li>,
                strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                em: ({ children }) => <em className="italic">{children}</em>,
                code: ({ children }) => <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                pre: ({ children }) => <pre className="bg-muted p-2 rounded overflow-x-auto text-xs">{children}</pre>,
                h1: ({ children }) => <h1 className="text-base font-semibold mb-2 text-foreground">{children}</h1>,
                h2: ({ children }) => <h2 className="text-sm font-semibold mb-2 text-foreground">{children}</h2>,
                h3: ({ children }) => <h3 className="text-sm font-medium mb-1 text-foreground">{children}</h3>,
              }}
            >
              {displayExplanation}
            </ReactMarkdown>
          </div>
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
    </motion.div>
  );
};

const ItemScoreResults: React.FC<ItemScoreResultsProps> = ({
  groupedResults,
  isLoading,
  error,
  itemId,
  onScoreResultSelect,
  selectedScoreResultId
}) => {
  const t = useTranslations('scorecards');
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
    <div className="space-y-1">
      <div className="flex items-end justify-between">
        <div className="flex items-center gap-1">
          <Box className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
          <h3 className="text-xl text-muted-foreground font-semibold">{t('scoreResults')}</h3>
        </div>
        {scorecardIds.length > 1 && (
          <div className="flex items-center gap-1 text-sm">
            <Box className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            <span>
              <span className="text-foreground font-medium"><NumberFlowWrapper value={totalResults} /></span> <span className="text-muted-foreground">{t(totalResults === 1 ? 'scoreResultAcross' : 'scoreResultsAcross')}</span> <span className="text-foreground font-medium"><NumberFlowWrapper value={scorecardIds.length} /></span> <span className="text-muted-foreground">{t(scorecardIds.length === 1 ? 'scorecard' : 'scorecards')}</span>
            </span>
          </div>
        )}
      </div>

      <div className="w-full space-y-4">
        {scorecardIds.map((scorecardId) => {
          const group = groupedResults[scorecardId];
          return (
            <div key={scorecardId}>
              <div className="mb-2">
                <div className="flex items-end justify-between">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-1">
                      <ListChecks className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      <span className="font-medium text-foreground">{group.scorecardName}</span>
                    </div>
                    {group.scorecardExternalId && (
                      <div>
                        <IdentifierDisplay 
                          externalId={group.scorecardExternalId}
                          iconSize="md"
                          textSize="xs"
                          displayMode="full"
                        />
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-sm">
                    <Box className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                    <span>
                      <span className="text-foreground font-medium"><NumberFlowWrapper value={group.scores.length} /></span> <span className="text-muted-foreground">{t(group.scores.length === 1 ? 'scoreResult' : 'scoreResults')}</span>
                    </span>
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                {group.scores.map((result) => (
                  <ScoreResultCard 
                    key={result.id} 
                    result={result}
                    onClick={() => onScoreResultSelect?.(result)}
                    isSelected={selectedScoreResultId === result.id}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ItemScoreResults;
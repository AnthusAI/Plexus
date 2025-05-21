"use client";

import React, { useRef, useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Code, List, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CardButton } from '@/components/CardButton';

export interface FeedbackItem {
  id: string;
  initialAnswerValue?: string;
  finalAnswerValue?: string;
  initialCommentValue?: string;
  finalCommentValue?: string;
  editCommentValue?: string;
  isAgreement?: boolean;
  scorecardId?: string;
  scoreId?: string;
  cacheKey?: string;
  createdAt?: string;
  updatedAt?: string;
  [key: string]: any; // Allow for additional fields
}

interface FeedbackItemViewProps {
  item: FeedbackItem;
  className?: string;
}

export const FeedbackItemView: React.FC<FeedbackItemViewProps> = ({ 
  item, 
  className 
}) => {
  // Format date to a more readable format
  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch (e) {
      return dateString;
    }
  };

  return (
    <div className={cn("p-3 mb-3 bg-muted rounded-md", className)}>
      <div className="grid grid-cols-2 gap-3">
        {/* Answer Values */}
        <div className="py-2">
          <div className="text-xs text-muted-foreground mb-1">Answer</div>
          <div className="text-sm">{item.initialAnswerValue || 'N/A'}</div>
        </div>
        <div className="py-2">
          <div className="text-xs text-muted-foreground mb-1">Answer</div>
          <div className="text-sm">{item.finalAnswerValue || 'N/A'}</div>
        </div>
        
        {/* Comment Values */}
        <div className="py-2">
          <div className="text-xs text-muted-foreground mb-1">Comment</div>
          <div className="text-sm whitespace-pre-wrap">{item.initialCommentValue || 'N/A'}</div>
        </div>
        <div className="py-2">
          <div className="text-xs text-muted-foreground mb-1">Comment</div>
          <div className="text-sm whitespace-pre-wrap">{item.finalCommentValue || 'N/A'}</div>
        </div>
      </div>
      
      {/* Metadata - spans full width */}
      <div className="mt-3 pt-2 border-t">
        <div className="grid grid-cols-1 gap-2">
          {item.editCommentValue && (
            <div>
              <div className="text-xs text-muted-foreground mb-1">Edit Comment</div>
              <div className="text-sm">{item.editCommentValue}</div>
            </div>
          )}
          
          <div className="grid grid-cols-2 gap-3 mt-2">
            <div>
              <div className="text-xs text-muted-foreground mb-1">Created</div>
              <div className="text-sm">{formatDate(item.createdAt)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Updated</div>
              <div className="text-sm">{formatDate(item.updatedAt)}</div>
            </div>
          </div>
          
          {item.isAgreement !== undefined && (
            <div className="mt-2">
              <div className="text-xs text-muted-foreground mb-1">Agreement Status</div>
              <div className="text-sm">
                {item.isAgreement 
                  ? <span className="text-green-600">Agreement</span> 
                  : <span className="text-red-600">Disagreement</span>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

interface FeedbackItemsListProps {
  items: FeedbackItem[];
  className?: string;
}

export const FeedbackItemsList: React.FC<FeedbackItemsListProps> = ({
  items,
  className
}) => {
  if (!items || items.length === 0) {
    return <p className="text-sm text-muted-foreground">No feedback items available</p>;
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="space-y-3 overflow-y-auto max-h-[500px] pr-1">
        {items.map((item) => (
          <FeedbackItemView key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
};

interface FeedbackItemsViewProps {
  items: FeedbackItem[];
  showRawJson: boolean;
  onToggleView: () => void;
  filterInfo?: {
    predicted: string;
    actual: string;
    count: number;
  };
  onClearFilter?: () => void;
  onClose?: () => void;
  isLoading?: boolean;
}

export const FeedbackItemsView: React.FC<FeedbackItemsViewProps> = ({
  items,
  showRawJson,
  onToggleView,
  filterInfo,
  onClose,
  isLoading = false
}) => {
  return (
    <div className="w-full overflow-hidden">
      {/* Header section */}
      <div className="flex justify-between items-center mb-3">
        <h4 className="text-base font-medium">
          Details
        </h4>
        {onClose && (
          <CardButton 
            icon={X}
            onClick={onClose}
            aria-label="Close details"
          />
        )}
      </div>

      {/* Filter info subheader with toggle button */}
      <div className="flex justify-between items-center mb-3">
        {filterInfo ? (
          <h5 className="text-sm text-muted-foreground">
            Filtered items: {filterInfo.count} - Predicted: {filterInfo.predicted}, Actual: {filterInfo.actual}
          </h5>
        ) : (
          <div>{/* Empty div to maintain layout */}</div>
        )}
        
        {items && items.length > 0 && (
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onToggleView} 
            className="h-auto p-1 flex items-center gap-1"
          >
            {showRawJson 
              ? <><List className="h-4 w-4" /> View as Items</>
              : <><Code className="h-4 w-4" /> View as JSON</>
            }
          </Button>
        )}
      </div>
      
      {/* Content area */}
      <div className="w-full overflow-hidden">
        {isLoading && (
          <p className="text-sm text-muted-foreground">Loading details...</p>
        )}
        
        {!isLoading && items && (
          <>
            {items.length > 0 ? (
              <>
                {showRawJson ? (
                  <pre className="whitespace-pre-wrap text-xs bg-white dark:bg-gray-800 dark:text-gray-200 overflow-y-auto overflow-x-auto font-mono max-h-[300px] px-2 py-2 max-w-full rounded">
                    {JSON.stringify(items, null, 2)}
                  </pre>
                ) : (
                  <div>
                    {/* Column headers at the top level */}
                    <div className="grid grid-cols-2 gap-3 mb-2">
                      <div className="font-medium text-sm ml-3">Before</div>
                      <div className="font-medium text-sm">After</div>
                    </div>
                    
                    <FeedbackItemsList items={items} />
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No items match the selected filter in the details file.</p>
            )}
          </>
        )}
        
        {!isLoading && !items && (
          <p className="text-sm text-muted-foreground">Click on the matrix above to load details.</p>
        )}
      </div>
    </div>
  );
};

export default FeedbackItemsList; 
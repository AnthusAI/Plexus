/**
 * Score Result Counter Utility
 * ===========================
 * 
 * This utility provides functions for counting score results for items
 * with pagination support and lazy loading capabilities.
 */

import { graphqlRequest } from './amplify-client';

export interface ScorecardCount {
  scorecardId: string;
  scorecardName: string;
  count: number;
}

export interface ScoreResultCount {
  itemId: string;
  count: number;
  isLoading: boolean;
  error?: string;
  scorecardBreakdown?: ScorecardCount[];
}

/**
 * Count score results for a specific item with scorecard breakdown
 * Uses pagination to handle large numbers of results
 */
export async function countScoreResultsForItem(itemId: string): Promise<{ 
  totalCount: number; 
  scorecardBreakdown: ScorecardCount[] 
}> {
  const scorecardCounts = new Map<string, { name: string; count: number }>();
  let totalCount = 0;
  let nextToken: string | null = null;
  
  try {
    do {
      const response: {
        data?: {
          listScoreResultByItemId?: {
            items: Array<{ 
              id: string;
              scorecardId: string;
              scorecard?: {
                name: string;
              };
            }>;
            nextToken: string | null;
          };
        };
        errors?: any[];
      } = await graphqlRequest<{
        listScoreResultByItemId: {
          items: Array<{ 
            id: string;
            scorecardId: string;
            scorecard?: {
              name: string;
            };
          }>;
          nextToken: string | null;
        }
      }>(`
        query CountScoreResultsByItemId($itemId: String!, $limit: Int!, $nextToken: String) {
          listScoreResultByItemId(
            itemId: $itemId,
            limit: $limit,
            nextToken: $nextToken
          ) {
            items {
              id
              scorecardId
              scorecard {
                name
              }
            }
            nextToken
          }
        }
      `, {
        itemId,
        limit: 1000, // Use large page size to minimize requests
        nextToken
      });
      
      if (response.data?.listScoreResultByItemId?.items) {
        const items = response.data.listScoreResultByItemId.items;
        totalCount += items.length;
        
        // Group by scorecard
        items.forEach(item => {
          const scorecardId = item.scorecardId;
          const scorecardName = item.scorecard?.name || 'Unnamed Scorecard';
          
          if (scorecardCounts.has(scorecardId)) {
            scorecardCounts.get(scorecardId)!.count++;
          } else {
            scorecardCounts.set(scorecardId, { name: scorecardName, count: 1 });
          }
        });
      }
      
      nextToken = response.data?.listScoreResultByItemId?.nextToken || null;
    } while (nextToken);
    
    // Convert map to array
    const scorecardBreakdown: ScorecardCount[] = Array.from(scorecardCounts.entries()).map(
      ([scorecardId, { name, count }]) => ({
        scorecardId,
        scorecardName: name,
        count
      })
    );
    
    return { totalCount, scorecardBreakdown };
  } catch (error) {
    console.error('Error counting score results for item:', itemId, error);
    throw error;
  }
}

/**
 * Lazy loading manager for score result counts
 * Uses Intersection Observer to only count visible items
 */
export class ScoreResultCountManager {
  private observer: IntersectionObserver | null = null;
  private countCache = new Map<string, ScoreResultCount>();
  private pendingCounts = new Set<string>();
  private callbacks = new Set<(counts: Map<string, ScoreResultCount>) => void>();
  
  constructor() {
    this.setupIntersectionObserver();
  }
  
  private setupIntersectionObserver() {
    if (typeof window === 'undefined') return;
    
    this.observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const itemId = entry.target.getAttribute('data-item-id');
            if (itemId && !this.countCache.has(itemId) && !this.pendingCounts.has(itemId)) {
              this.loadCountForItem(itemId);
            }
          }
        });
      },
      {
        root: null,
        rootMargin: '50px',
        threshold: 0.1
      }
    );
  }
  
  /**
   * Observe an item element for lazy loading
   */
  observeItem(element: Element, itemId: string) {
    if (!this.observer) return;
    
    element.setAttribute('data-item-id', itemId);
    this.observer.observe(element);
  }
  
  /**
   * Stop observing an item element
   */
  unobserveItem(element: Element) {
    if (!this.observer) return;
    this.observer.unobserve(element);
  }
  
  /**
   * Force load count for a specific item (used for updates)
   */
  async loadCountForItem(itemId: string, showLoading: boolean = true) {
    // Prevent duplicate concurrent requests for the same item
    if (this.pendingCounts.has(itemId)) {
      return;
    }
    
    this.pendingCounts.add(itemId);
    
    // Only show loading state if explicitly requested and we don't have existing data,
    // or if we have no data at all
    const existingCount = this.countCache.get(itemId);
    if (showLoading && (!existingCount || existingCount.count === 0)) {
      this.countCache.set(itemId, {
        itemId,
        count: existingCount?.count || 0,
        isLoading: true,
        // PRESERVE existing scorecardBreakdown to prevent flicker
        scorecardBreakdown: existingCount?.scorecardBreakdown || []
      });
      this.notifyCallbacks();
    }
    
    try {
      const { totalCount, scorecardBreakdown } = await countScoreResultsForItem(itemId);
      
      this.countCache.set(itemId, {
        itemId,
        count: totalCount,
        isLoading: false,
        scorecardBreakdown
      });
    } catch (error) {
      this.countCache.set(itemId, {
        itemId,
        count: existingCount?.count || 0,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        scorecardBreakdown: existingCount?.scorecardBreakdown || []
      });
    } finally {
      this.pendingCounts.delete(itemId);
      this.notifyCallbacks();
    }
  }
  
  /**
   * Get the current count for an item
   */
  getCount(itemId: string): ScoreResultCount {
    return this.countCache.get(itemId) || {
      itemId,
      count: 0,
      isLoading: false
    };
  }
  
  /**
   * Clear count for an item (forces reload on next observation)
   * Use this when you want the next loadCountForItem to show a loading state
   */
  clearCount(itemId: string) {
    const wasInCache = this.countCache.has(itemId);
    const wasInPending = this.pendingCounts.has(itemId);
    
    this.countCache.delete(itemId);
    this.pendingCounts.delete(itemId);
    
    // Notify callbacks immediately so UI shows loading state
    this.notifyCallbacks();
  }

  /**
   * Force refresh count for a specific item immediately
   */
  refreshItemCount(itemId: string) {
    // Always refresh immediately, regardless of cache status
    // This ensures selected items get priority updates
    this.loadCountForItem(itemId, false);
  }

  private batchedItemIds = new Set<string>();
  private batchTimeout: NodeJS.Timeout | null = null;

  /**
   * Batch refresh multiple items efficiently
   */
  private processBatchedRefresh() {
    if (this.batchedItemIds.size === 0) return;
    
    // Process all batched items
    const itemIds = Array.from(this.batchedItemIds);
    this.batchedItemIds.clear();
    
    // Load counts for all items in parallel without showing loading states
    // to prevent flickering during bulk refreshes
    Promise.all(itemIds.map(itemId => this.loadCountForItem(itemId, false)));
  }

  /**
   * Refresh all cached item counts with batching
   */
  refreshAllCounts() {
    // Add all cached items to the batch
    for (const itemId of this.countCache.keys()) {
      this.batchedItemIds.add(itemId);
    }
    
    // Clear any existing timeout
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
    }
    
    // Process the batch after a short delay to collect more items
    this.batchTimeout = setTimeout(() => {
      this.processBatchedRefresh();
      this.batchTimeout = null;
    }, 500); // Reduced from 1000ms to 500ms for better responsiveness
  }
  
  /**
   * Subscribe to count changes
   */
  subscribe(callback: (counts: Map<string, ScoreResultCount>) => void) {
    this.callbacks.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.callbacks.delete(callback);
    };
  }
  
  private notifyCallbacks() {
    this.callbacks.forEach(callback => {
      callback(new Map(this.countCache));
    });
  }
  
  /**
   * Cleanup resources
   */
  destroy() {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
      this.batchTimeout = null;
    }
    this.countCache.clear();
    this.pendingCounts.clear();
    this.callbacks.clear();
  }
}
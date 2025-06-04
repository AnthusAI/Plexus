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
  async loadCountForItem(itemId: string) {
    // Allow multiple requests for the same item to ensure we get the latest data
    // Remove the pending check to be more aggressive about refreshing
    this.pendingCounts.add(itemId);
    
    // Only show loading state if we don't already have cached data
    const existingCount = this.countCache.get(itemId);
    if (!existingCount || existingCount.count === 0) {
      this.countCache.set(itemId, {
        itemId,
        count: 0,
        isLoading: true
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
        count: 0,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Unknown error'
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
   */
  clearCount(itemId: string) {
    console.log('📊 Clearing count cache for item:', itemId);
    const wasInCache = this.countCache.has(itemId);
    const wasInPending = this.pendingCounts.has(itemId);
    
    this.countCache.delete(itemId);
    this.pendingCounts.delete(itemId);
    
    console.log('📊 Count cleared for item:', itemId, { wasInCache, wasInPending });
    
    // Notify callbacks immediately so UI shows loading state
    this.notifyCallbacks();
  }

  /**
   * Force refresh count for an item if it exists in cache
   */
  refreshItemCount(itemId: string) {
    console.log('📊 Refresh requested for item:', itemId);
    if (this.countCache.has(itemId)) {
      console.log('📊 Item in cache, clearing and reloading:', itemId);
      this.clearCount(itemId);
      this.loadCountForItem(itemId);
    } else {
      console.log('📊 Item not in cache, skipping refresh:', itemId);
    }
  }

  private refreshTimeout: NodeJS.Timeout | null = null;

  /**
   * Refresh all cached item counts (throttled to prevent excessive API calls)
   */
  refreshAllCounts() {
    // Clear any existing timeout
    if (this.refreshTimeout) {
      clearTimeout(this.refreshTimeout);
    }
    
    // Throttle the refresh to avoid too many API calls
    this.refreshTimeout = setTimeout(() => {
      const itemIds = Array.from(this.countCache.keys());
      itemIds.forEach(itemId => {
        // Don't clear the cache - just reload in the background
        this.loadCountForItem(itemId);
      });
      this.refreshTimeout = null;
    }, 1000); // 1 second throttle
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
    if (this.refreshTimeout) {
      clearTimeout(this.refreshTimeout);
      this.refreshTimeout = null;
    }
    this.countCache.clear();
    this.pendingCounts.clear();
    this.callbacks.clear();
  }
}
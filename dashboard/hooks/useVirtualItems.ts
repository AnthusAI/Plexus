import { useEffect, useState, useRef, useCallback } from 'react';

interface UseVirtualItemsOptions {
  items: any[];
  itemRefsMap: React.MutableRefObject<Map<string, HTMLDivElement | null>>;
  selectedItemId?: string | null;
  bufferRows?: number;
}

interface UseVirtualItemsReturn {
  visibleItemIds: Set<string>;
  shouldRenderItem: (itemId: string) => boolean;
}

/**
 * Hook for viewport-based virtual scrolling of items.
 * Only renders items that are visible in the viewport plus a buffer zone.
 * 
 * @param items - Array of items to virtualize
 * @param itemRefsMap - Map of item IDs to their DOM elements
 * @param selectedItemId - ID of currently selected item (always rendered)
 * @param bufferRows - Number of rows to keep above/below viewport (default: 2)
 */
export function useVirtualItems({
  items,
  itemRefsMap,
  selectedItemId = null,
  bufferRows = 2,
}: UseVirtualItemsOptions): UseVirtualItemsReturn {
  const [visibleItemIds, setVisibleItemIds] = useState<Set<string>>(new Set());
  const observerRef = useRef<IntersectionObserver | null>(null);
  const itemVisibilityRef = useRef<Map<string, boolean>>(new Map());
  
  // Calculate buffer margin based on viewport height and buffer rows
  // Assuming average item height is ~200px and ~6 items per row on average
  const bufferMargin = useCallback(() => {
    // Use a generous buffer: viewport height * bufferRows factor
    // This ensures smooth scrolling without items popping in/out
    const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 1000;
    const bufferPixels = Math.floor(viewportHeight * bufferRows * 0.5);
    return `${bufferPixels}px`;
  }, [bufferRows]);

  // Update visible items based on intersection changes
  const updateVisibleItems = useCallback(() => {
    const newVisibleIds = new Set<string>();
    
    // Always include selected item
    if (selectedItemId) {
      newVisibleIds.add(selectedItemId);
    }
    
    // Add all items that are currently intersecting
    itemVisibilityRef.current.forEach((isVisible, itemId) => {
      if (isVisible) {
        newVisibleIds.add(itemId);
      }
    });
    
    setVisibleItemIds(newVisibleIds);
  }, [selectedItemId]);

  // Set up intersection observer
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const margin = bufferMargin();
    
    // Create intersection observer with buffer margin
    observerRef.current = new IntersectionObserver(
      (entries) => {
        let hasChanges = false;
        
        entries.forEach((entry) => {
          const itemId = entry.target.getAttribute('data-item-id');
          if (!itemId) return;
          
          const wasVisible = itemVisibilityRef.current.get(itemId);
          const isVisible = entry.isIntersecting;
          
          if (wasVisible !== isVisible) {
            itemVisibilityRef.current.set(itemId, isVisible);
            hasChanges = true;
          }
        });
        
        if (hasChanges) {
          updateVisibleItems();
        }
      },
      {
        root: null, // Use viewport as root
        rootMargin: margin,
        threshold: 0, // Trigger as soon as any part is visible
      }
    );

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [bufferMargin, updateVisibleItems]);

  // Observe all items when they mount or items array changes
  useEffect(() => {
    if (!observerRef.current) return;

    const observer = observerRef.current;
    
    // Observe all current items
    items.forEach((item) => {
      const element = itemRefsMap.current.get(item.id);
      if (element) {
        // Add data attribute for identification
        element.setAttribute('data-item-id', item.id);
        observer.observe(element);
      }
    });

    // Cleanup: unobserve items that are no longer in the list
    const currentItemIds = new Set(items.map(item => item.id));
    itemVisibilityRef.current.forEach((_, itemId) => {
      if (!currentItemIds.has(itemId)) {
        itemVisibilityRef.current.delete(itemId);
      }
    });

    return () => {
      // Unobserve all on cleanup
      items.forEach((item) => {
        const element = itemRefsMap.current.get(item.id);
        if (element) {
          observer.unobserve(element);
        }
      });
    };
  }, [items, itemRefsMap]);

  // Update visible items when selected item changes
  useEffect(() => {
    updateVisibleItems();
  }, [selectedItemId, updateVisibleItems]);

  // Initialize with all items visible initially, let IntersectionObserver handle virtualization
  useEffect(() => {
    if (items.length === 0) return;
    
    // On initial load or when items change significantly, mark all as visible
    // The IntersectionObserver will quickly update this to only visible items
    if (visibleItemIds.size === 0) {
      const allIds = new Set(items.map(item => item.id));
      if (selectedItemId) {
        allIds.add(selectedItemId);
      }
      setVisibleItemIds(allIds);
      
      // Mark them as visible in the ref initially
      allIds.forEach(id => {
        itemVisibilityRef.current.set(id, true);
      });
    } else {
      // When new items are added, add them to visible set
      // IntersectionObserver will remove them if they're off-screen
      const newItemIds = items
        .filter(item => !itemVisibilityRef.current.has(item.id))
        .map(item => item.id);
      
      if (newItemIds.length > 0) {
        setVisibleItemIds(prev => {
          const newSet = new Set(prev);
          newItemIds.forEach(id => {
            newSet.add(id);
            itemVisibilityRef.current.set(id, true);
          });
          return newSet;
        });
      }
    }
  }, [items, selectedItemId, visibleItemIds.size]);

  const shouldRenderItem = useCallback(
    (itemId: string) => {
      // Always render selected item
      if (itemId === selectedItemId) return true;
      
      // Render if in visible set
      return visibleItemIds.has(itemId);
    },
    [visibleItemIds, selectedItemId]
  );

  return {
    visibleItemIds,
    shouldRenderItem,
  };
}


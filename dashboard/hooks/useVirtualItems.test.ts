import { renderHook, act, waitFor } from '@testing-library/react';
import { useVirtualItems } from './useVirtualItems';
import { useRef } from 'react';

// Mock IntersectionObserver
class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | null = null;
  readonly rootMargin: string = '';
  readonly thresholds: ReadonlyArray<number> = [];
  
  private callback: IntersectionObserverCallback;
  private elements: Map<Element, boolean> = new Map();

  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.rootMargin = options?.rootMargin || '';
  }

  observe(target: Element): void {
    this.elements.set(target, true);
    // Simulate immediate intersection for newly observed elements
    setTimeout(() => {
      const entry: IntersectionObserverEntry = {
        target,
        isIntersecting: true,
        intersectionRatio: 1,
        boundingClientRect: target.getBoundingClientRect(),
        intersectionRect: target.getBoundingClientRect(),
        rootBounds: null,
        time: Date.now(),
      };
      this.callback([entry], this);
    }, 0);
  }

  unobserve(target: Element): void {
    this.elements.delete(target);
  }

  disconnect(): void {
    this.elements.clear();
  }

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

// Set up global IntersectionObserver mock
global.IntersectionObserver = MockIntersectionObserver as any;

describe('useVirtualItems', () => {
  const createMockItems = (count: number) => {
    return Array.from({ length: count }, (_, i) => ({
      id: `item-${i}`,
      timestamp: new Date().toISOString(),
      scorecards: [],
      accountId: 'test-account',
      isEvaluation: false,
    }));
  };

  const createMockRefs = (items: any[]) => {
    const map = new Map<string, HTMLDivElement | null>();
    items.forEach(item => {
      const div = document.createElement('div');
      div.setAttribute('data-item-id', item.id);
      map.set(item.id, div);
    });
    return { current: map };
  };

  it('should initialize with all items visible', async () => {
    const items = createMockItems(100);
    const itemRefsMap = createMockRefs(items);

    const { result } = renderHook(() =>
      useVirtualItems({
        items,
        itemRefsMap,
        selectedItemId: null,
        bufferRows: 2,
      })
    );

    await waitFor(() => {
      expect(result.current.visibleItemIds.size).toBeGreaterThan(0);
    });

    // Should show all items initially (IntersectionObserver will filter)
    expect(result.current.visibleItemIds.size).toBe(100);
    
    // First item should be visible
    expect(result.current.shouldRenderItem('item-0')).toBe(true);
  });

  it('should always render selected item', async () => {
    const items = createMockItems(100);
    const itemRefsMap = createMockRefs(items);
    const selectedItemId = 'item-50';

    const { result } = renderHook(() =>
      useVirtualItems({
        items,
        itemRefsMap,
        selectedItemId,
        bufferRows: 2,
      })
    );

    await waitFor(() => {
      expect(result.current.visibleItemIds.size).toBeGreaterThan(0);
    });

    // Selected item should always be rendered
    expect(result.current.shouldRenderItem(selectedItemId)).toBe(true);
  });

  it('should handle new items added at the top', async () => {
    const initialItems = createMockItems(50);
    const itemRefsMap = createMockRefs(initialItems);

    const { result, rerender } = renderHook(
      ({ items }) =>
        useVirtualItems({
          items,
          itemRefsMap,
          selectedItemId: null,
          bufferRows: 2,
        }),
      { initialProps: { items: initialItems } }
    );

    await waitFor(() => {
      expect(result.current.visibleItemIds.size).toBeGreaterThan(0);
    });

    // Add new items at the top
    const newItem = {
      id: 'item-new',
      timestamp: new Date().toISOString(),
      scorecards: [],
      accountId: 'test-account',
      isEvaluation: false,
    };
    const updatedItems = [newItem, ...initialItems];
    
    // Add ref for new item
    const div = document.createElement('div');
    div.setAttribute('data-item-id', newItem.id);
    itemRefsMap.current.set(newItem.id, div);

    rerender({ items: updatedItems });

    await waitFor(() => {
      expect(result.current.shouldRenderItem('item-new')).toBe(true);
    });

    // New item at top should be visible
    expect(result.current.shouldRenderItem('item-new')).toBe(true);
  });

  it('should update visible items when selected item changes', async () => {
    const items = createMockItems(100);
    const itemRefsMap = createMockRefs(items);

    const { result, rerender } = renderHook(
      ({ selectedItemId }) =>
        useVirtualItems({
          items,
          itemRefsMap,
          selectedItemId,
          bufferRows: 2,
        }),
      { initialProps: { selectedItemId: null } }
    );

    await waitFor(() => {
      expect(result.current.visibleItemIds.size).toBeGreaterThan(0);
    });

    // Initially item-80 might not be visible
    const initiallyVisible = result.current.shouldRenderItem('item-80');

    // Change selected item
    rerender({ selectedItemId: 'item-80' });

    await waitFor(() => {
      expect(result.current.shouldRenderItem('item-80')).toBe(true);
    });

    // Now item-80 should definitely be visible
    expect(result.current.shouldRenderItem('item-80')).toBe(true);
  });

  it('should handle empty items array', () => {
    const itemRefsMap = { current: new Map() };

    const { result } = renderHook(() =>
      useVirtualItems({
        items: [],
        itemRefsMap,
        selectedItemId: null,
        bufferRows: 2,
      })
    );

    expect(result.current.visibleItemIds.size).toBe(0);
  });

  it('should use custom buffer rows', async () => {
    const items = createMockItems(100);
    const itemRefsMap = createMockRefs(items);

    const { result: result1 } = renderHook(() =>
      useVirtualItems({
        items,
        itemRefsMap,
        selectedItemId: null,
        bufferRows: 1,
      })
    );

    const { result: result2 } = renderHook(() =>
      useVirtualItems({
        items,
        itemRefsMap,
        selectedItemId: null,
        bufferRows: 4,
      })
    );

    await waitFor(() => {
      expect(result1.current.visibleItemIds.size).toBeGreaterThan(0);
      expect(result2.current.visibleItemIds.size).toBeGreaterThan(0);
    });

    // Both should initialize with same initial items
    // Buffer rows affect the IntersectionObserver rootMargin, not initial load
    expect(result1.current.visibleItemIds.size).toBeGreaterThan(0);
    expect(result2.current.visibleItemIds.size).toBeGreaterThan(0);
  });

});


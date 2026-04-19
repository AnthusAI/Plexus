"use client";

import React from "react";

interface UseIncrementalRowsOptions {
  initialCount?: number;
  pageSize?: number;
}

interface UseIncrementalRowsResult<T> {
  visibleRows: T[];
  visibleCount: number;
  totalCount: number;
  hasMore: boolean;
  loadMore: () => void;
  sentinelRef: React.RefObject<HTMLDivElement | null>;
}

/**
 * Render table rows incrementally to avoid mounting very large lists at once.
 */
export function useIncrementalRows<T>(
  rows: T[],
  options: UseIncrementalRowsOptions = {}
): UseIncrementalRowsResult<T> {
  const initialCount = options.initialCount ?? 100;
  const pageSize = options.pageSize ?? 100;
  const [visibleCount, setVisibleCount] = React.useState(initialCount);
  const sentinelRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    setVisibleCount(initialCount);
  }, [rows, initialCount]);

  const hasMore = visibleCount < rows.length;

  const loadMore = React.useCallback(() => {
    setVisibleCount((current) => Math.min(current + pageSize, rows.length));
  }, [pageSize, rows.length]);

  React.useEffect(() => {
    if (!hasMore) return;

    const target = sentinelRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            loadMore();
            break;
          }
        }
      },
      {
        root: null,
        rootMargin: "240px",
        threshold: 0.01,
      }
    );

    observer.observe(target);

    return () => {
      observer.disconnect();
    };
  }, [hasMore, loadMore]);

  return {
    visibleRows: rows.slice(0, visibleCount),
    visibleCount: Math.min(visibleCount, rows.length),
    totalCount: rows.length,
    hasMore,
    loadMore,
    sentinelRef,
  };
}

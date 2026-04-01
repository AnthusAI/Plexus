import { useEffect, type RefObject } from 'react'

export function useResizeObserver<T extends Element>(
  ref: RefObject<T | null>,
  callback: (entry: ResizeObserverEntry) => void
) {
  useEffect(() => {
    if (!ref.current) return

    const observer = new ResizeObserver((entries) => {
      callback(entries[0])
    })

    observer.observe(ref.current)

    return () => {
      observer.disconnect()
    }
  }, [ref, callback])
} 

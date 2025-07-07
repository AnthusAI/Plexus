'use client'

import { useState, useEffect, createContext, useContext } from 'react'
import { usePathname } from 'next/navigation'

interface LoadingContextType {
  isLoading: boolean
  loadingRoute: string | null
  startLoading: (route: string) => void
  stopLoading: () => void
}

const LoadingContext = createContext<LoadingContextType>({
  isLoading: false,
  loadingRoute: null,
  startLoading: () => {},
  stopLoading: () => {}
})

export function LoadingProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(false)
  const [loadingRoute, setLoadingRoute] = useState<string | null>(null)
  const pathname = usePathname()

  useEffect(() => {
    // Reset loading state when pathname changes (navigation complete)
    setIsLoading(false)
    setLoadingRoute(null)
  }, [pathname])

  const startLoading = (route: string) => {
    setIsLoading(true)
    setLoadingRoute(route)
  }

  const stopLoading = () => {
    setIsLoading(false)
    setLoadingRoute(null)
  }

  return (
    <LoadingContext.Provider value={{ isLoading, loadingRoute, startLoading, stopLoading }}>
      {children}
    </LoadingContext.Provider>
  )
}

export function useLoading() {
  return useContext(LoadingContext)
}

// Smart Link component that automatically handles loading states
import Link from 'next/link'

interface SmartLinkProps {
  href: string
  children: React.ReactNode
  className?: string
  onClick?: () => void
}

export function SmartLink({ href, children, className, onClick }: SmartLinkProps) {
  const { startLoading } = useLoading()
  const pathname = usePathname()

  const handleClick = () => {
    if (href !== pathname) {
      startLoading(href)
    }
    onClick?.()
  }

  return (
    <Link href={href} className={className} onClick={handleClick}>
      {children}
    </Link>
  )
}

// Loading indicator component
export function LoadingIndicator() {
  const { isLoading, loadingRoute } = useLoading()

  if (!isLoading) return null

  return (
    <div className="fixed top-0 left-0 right-0 z-50">
      <div className="h-1 bg-primary/20">
        <div className="h-full bg-primary animate-loading-bar"></div>
      </div>
      {loadingRoute && (
        <div className="absolute top-1 right-4 text-xs text-primary bg-background px-2 py-1 rounded shadow">
          Loading...
        </div>
      )}
    </div>
  )
}
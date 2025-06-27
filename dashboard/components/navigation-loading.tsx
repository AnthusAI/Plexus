'use client'

import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'

interface NavigationLoadingProps {
  children: React.ReactNode
  skeletonComponent?: React.ComponentType
}

export function NavigationLoading({ children, skeletonComponent: SkeletonComponent }: NavigationLoadingProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [showSkeleton, setShowSkeleton] = useState(false)
  const pathname = usePathname()

  useEffect(() => {
    // Reset loading state when pathname changes
    setIsLoading(false)
    setShowSkeleton(false)
  }, [pathname])

  const handleNavigation = () => {
    setIsLoading(true)
    setShowSkeleton(true)
    
    // Show skeleton for minimum 300ms to avoid flash
    setTimeout(() => {
      setShowSkeleton(false)
    }, 300)
  }

  return (
    <div className="relative h-full">
      <AnimatePresence mode="wait">
        {showSkeleton && SkeletonComponent ? (
          <motion.div
            key="skeleton"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="absolute inset-0 z-10"
          >
            <SkeletonComponent />
          </motion.div>
        ) : (
          <motion.div
            key="content"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="h-full"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// Hook for triggering navigation loading
export function useNavigationLoading() {
  const [isLoading, setIsLoading] = useState(false)
  const pathname = usePathname()

  useEffect(() => {
    setIsLoading(false)
  }, [pathname])

  const startLoading = () => setIsLoading(true)
  const stopLoading = () => setIsLoading(false)

  return { isLoading, startLoading, stopLoading }
}
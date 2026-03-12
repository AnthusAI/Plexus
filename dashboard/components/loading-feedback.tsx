'use client'

import { useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, Clock, AlertCircle } from 'lucide-react'

interface LoadingFeedbackProps {
  showFeedback?: boolean
  onComplete?: () => void
}

export function LoadingFeedback({ showFeedback = true, onComplete }: LoadingFeedbackProps) {
  const [loadingState, setLoadingState] = useState<'loading' | 'success' | 'error' | null>(null)
  const [currentPage, setCurrentPage] = useState<string>('')
  const pathname = usePathname()

  useEffect(() => {
    if (showFeedback) {
      setLoadingState('loading')
      
      // Get page name from pathname
      const pageName = pathname.split('/').pop() || 'page'
      setCurrentPage(pageName.charAt(0).toUpperCase() + pageName.slice(1))

      // Simulate loading completion
      const timer = setTimeout(() => {
        setLoadingState('success')
        
        // Hide success message after 2 seconds
        setTimeout(() => {
          setLoadingState(null)
          onComplete?.()
        }, 2000)
      }, 500)

      return () => clearTimeout(timer)
    }
  }, [pathname, showFeedback, onComplete])

  return (
    <AnimatePresence>
      {loadingState && (
        <motion.div
          initial={{ opacity: 0, y: -50 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -50 }}
          className="fixed top-4 right-4 z-50"
        >
          <div className="flex items-center space-x-2 bg-background border rounded-lg shadow-lg p-3">
            {loadingState === 'loading' && (
              <>
                <Clock className="h-4 w-4 text-primary animate-pulse" />
                <span className="text-sm">Loading {currentPage}...</span>
              </>
            )}
            {loadingState === 'success' && (
              <>
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-sm">{currentPage} loaded</span>
              </>
            )}
            {loadingState === 'error' && (
              <>
                <AlertCircle className="h-4 w-4 text-red-500" />
                <span className="text-sm">Error loading {currentPage}</span>
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Page transition wrapper with loading states
export function PageTransition({ 
  children, 
  className = "",
  showLoadingFeedback = true 
}: { 
  children: React.ReactNode
  className?: string
  showLoadingFeedback?: boolean
}) {
  const [isVisible, setIsVisible] = useState(false)
  const pathname = usePathname()

  useEffect(() => {
    setIsVisible(false)
    const timer = setTimeout(() => setIsVisible(true), 100)
    return () => clearTimeout(timer)
  }, [pathname])

  return (
    <>
      {showLoadingFeedback && <LoadingFeedback />}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: isVisible ? 1 : 0, y: isVisible ? 0 : 20 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className={className}
      >
        {children}
      </motion.div>
    </>
  )
}
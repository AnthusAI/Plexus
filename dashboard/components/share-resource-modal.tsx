"use client"

import { useState, useEffect, useRef } from "react"
import { Calendar } from "@/components/ui/calendar"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from "@/components/ui/select"
import { ShareLinkViewOptions } from "@/utils/share-link-client"
import * as React from "react"
import { createPortal } from "react-dom"

interface ShareResourceModalProps {
  isOpen: boolean
  onClose: () => void
  onShare: (expiresAt: string, viewOptions: ShareLinkViewOptions) => Promise<void>
  resourceType: 'Evaluation' | 'Scorecard' | 'Report' | string
  resourceName?: string
}

export function ShareResourceModal({ 
  isOpen, 
  onClose, 
  onShare, 
  resourceType, 
  resourceName 
}: ShareResourceModalProps) {
  // Default expiration date (30 days from now)
  const defaultExpirationDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
  
  // State for form values
  const [expirationDate, setExpirationDate] = useState<Date>(defaultExpirationDate)
  const [displayMode, setDisplayMode] = useState<"summary" | "detailed">("detailed")
  const [includeMetrics, setIncludeMetrics] = useState(true)
  const [includeCostInfo, setIncludeCostInfo] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isMounted, setIsMounted] = useState(false)
  
  // Reference to track if we're in the process of closing
  const isClosingRef = useRef(false)
  
  // Handle client-side mounting
  useEffect(() => {
    setIsMounted(true)
    return () => setIsMounted(false)
  }, [])
  
  // Reset form values when modal opens
  useEffect(() => {
    if (isOpen) {
      // Reset form values when opening
      setExpirationDate(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000))
      setDisplayMode("detailed")
      setIncludeMetrics(true)
      setIncludeCostInfo(false)
      setIsSubmitting(false)
      isClosingRef.current = false
      
      // Prevent body scrolling when modal is open
      document.body.style.overflow = 'hidden'
    } else {
      // Re-enable body scrolling when modal is closed
      document.body.style.overflow = ''
    }
  }, [isOpen])
  
  // Cleanup effect to ensure body styles are reset
  useEffect(() => {
    // Cleanup function to ensure body styles are reset when component unmounts
    return () => {
      document.body.style.overflow = ''
      document.body.style.pointerEvents = ''
    }
  }, [])
  
  // Get title and description based on resource type
  const getModalTitle = () => {
    return `Share ${resourceName || resourceType}`
  }
  
  const getModalDescription = () => {
    return `Configure sharing options for this ${resourceType.toLowerCase()}`
  }
  
  // Handle form submission
  const handleSubmit = async () => {
    if (isClosingRef.current) return
    
    setIsSubmitting(true)
    
    try {
      // Create view options object
      const viewOptions: ShareLinkViewOptions = {
        displayMode,
        includeMetrics,
        includeCostInfo
      }
      
      // Call the onShare callback with the configured values
      await onShare(expirationDate.toISOString(), viewOptions)
      
      // Mark as closing and close the modal
      isClosingRef.current = true
      onClose()
    } catch (error) {
      console.error(`Error sharing ${resourceType}:`, error)
    } finally {
      setIsSubmitting(false)
    }
  }
  
  // Safe close handler
  const handleSafeClose = () => {
    if (isClosingRef.current) return
    isClosingRef.current = true
    
    // Re-enable body scrolling
    document.body.style.overflow = ''
    
    // Close the modal
    onClose()
  }
  
  // Handle backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      handleSafeClose()
    }
  }
  
  // If not open or not mounted, don't render anything
  if (!isOpen || !isMounted) return null
  
  // Create portal content
  const modalContent = (
    <div 
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center"
      onClick={handleBackdropClick}
    >
      <div 
        className="bg-background rounded-lg shadow-lg w-full max-w-md mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">{getModalTitle()}</h2>
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-6 w-6" 
              onClick={handleSafeClose}
            >
              <span className="sr-only">Close</span>
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </Button>
          </div>
          
          <p className="text-sm text-muted-foreground mb-4">
            {getModalDescription()}
          </p>
          
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="expiration">Expiration Date</Label>
              <div className="border rounded-md p-1">
                <Calendar
                  mode="single"
                  selected={expirationDate}
                  onSelect={(date) => date && setExpirationDate(date)}
                  disabled={(date) => date < new Date()}
                  initialFocus
                />
              </div>
            </div>
            
            <div className="grid gap-2">
              <Label htmlFor="displayMode">Display Mode</Label>
              <Select value={displayMode} onValueChange={(value: "summary" | "detailed") => setDisplayMode(value)}>
                <SelectTrigger id="displayMode">
                  <SelectValue placeholder="Select display mode" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="summary">Summary</SelectItem>
                  <SelectItem value="detailed">Detailed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="flex items-center space-x-2">
              <Checkbox 
                id="includeMetrics" 
                checked={includeMetrics} 
                onCheckedChange={(checked) => setIncludeMetrics(checked === true)}
              />
              <Label htmlFor="includeMetrics">Include Metrics</Label>
            </div>
            
            <div className="flex items-center space-x-2">
              <Checkbox 
                id="includeCostInfo" 
                checked={includeCostInfo} 
                onCheckedChange={(checked) => setIncludeCostInfo(checked === true)}
              />
              <Label htmlFor="includeCostInfo">Include Cost Information</Label>
            </div>
          </div>
          
          <div className="flex justify-end space-x-2 mt-4">
            <Button variant="outline" type="button" onClick={handleSafeClose}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting ? "Creating..." : "Create Share Link"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
  
  // Use createPortal to render the modal outside the normal DOM hierarchy
  return createPortal(modalContent, document.body)
} 
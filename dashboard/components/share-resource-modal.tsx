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
import { format, addDays } from "date-fns"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { CalendarIcon } from "lucide-react"
import { cn } from "@/lib/utils"

// Define common expiration periods
const EXPIRATION_PERIODS = [
  { value: "7days", label: "7 days", days: 7 },
  { value: "30days", label: "30 days", days: 30 },
  { value: "90days", label: "90 days", days: 90 },
  { value: "180days", label: "6 months", days: 180 },
  { value: "365days", label: "1 year", days: 365 },
  { value: "never", label: "Never", days: null },
  { value: "custom", label: "Custom date", days: null }
];

interface ShareResourceModalProps {
  isOpen: boolean
  onClose: () => void
  onShare: (expiresAt: string, viewOptions: ShareLinkViewOptions) => Promise<void>
  resourceType: 'Evaluation' | 'Scorecard' | 'Report' | string
  resourceName?: string
  shareUrl?: string | null
}

export function ShareResourceModal({ 
  isOpen, 
  onClose, 
  onShare, 
  resourceType, 
  resourceName,
  shareUrl
}: ShareResourceModalProps) {
  // Default expiration date (30 days from now)
  const defaultExpirationDate = addDays(new Date(), 30)
  
  // State for form values
  const [expirationDate, setExpirationDate] = useState<Date | null>(defaultExpirationDate)
  const [expirationPeriod, setExpirationPeriod] = useState<string>("30days")
  const [isCustomDate, setIsCustomDate] = useState<boolean>(false)
  const [displayMode, setDisplayMode] = useState<"summary" | "detailed">("detailed")
  const [includeMetrics, setIncludeMetrics] = useState(true)
  const [includeCostInfo, setIncludeCostInfo] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isMounted, setIsMounted] = useState(false)
  const [calendarOpen, setCalendarOpen] = useState(false)
  
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
      setExpirationDate(defaultExpirationDate)
      setExpirationPeriod("30days")
      setIsCustomDate(false)
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
  
  // Handle expiration period change
  const handleExpirationPeriodChange = (value: string) => {
    setExpirationPeriod(value);
    
    if (value === "custom") {
      setIsCustomDate(true);
    } else {
      setIsCustomDate(false);
      
      if (value === "never") {
        // For "never expires", set expirationDate to null
        setExpirationDate(null);
      } else {
        // Set the expiration date based on the selected period
        const period = EXPIRATION_PERIODS.find(p => p.value === value);
        if (period && period.days) {
          setExpirationDate(addDays(new Date(), period.days));
        }
      }
    }
  };
  
  // Get title and description based on resource type
  const getModalTitle = () => {
    return `Share ${resourceName || resourceType}`
  }
  
  const getModalDescription = () => {
    return `Configure sharing options for this ${resourceType.toLowerCase()}`
  }
  
  // Handler for form submission
  const handleSubmit = async () => {
    if (isClosingRef.current) return
    
    setIsSubmitting(true)
    
    try {
      // Create view options object - only include properties relevant to the resource type
      const viewOptions: ShareLinkViewOptions = {};
      
      // Only include evaluation-specific options for evaluation resources
      if (resourceType === 'Evaluation') {
        viewOptions.displayMode = displayMode;
        viewOptions.includeMetrics = includeMetrics;
        viewOptions.includeCostInfo = includeCostInfo;
      }
      
      // Call the onShare callback with the configured values
      // If expirationDate is null (never expires), pass undefined for expiresAt
      const expiresAt = expirationDate ? expirationDate.toISOString() : undefined;
      await onShare(expiresAt as string, viewOptions)
      
      // Don't automatically close the modal - let the parent component decide
      // The parent will close it if the clipboard operation succeeds
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
          
          {/* Display share URL if available */}
          {shareUrl && (
            <div className="mb-4 p-3 bg-muted rounded-md">
              <Label htmlFor="shareUrl" className="text-sm font-medium mb-1 block">Share Link</Label>
              <div className="flex gap-2">
                <input
                  id="shareUrl"
                  type="text"
                  value={shareUrl}
                  readOnly
                  className="flex-1 px-3 py-2 text-sm border rounded-md bg-background"
                  onClick={(e) => e.currentTarget.select()}
                />
                <Button 
                  size="sm" 
                  onClick={() => {
                    navigator.clipboard.writeText(shareUrl)
                      .then(() => {
                        // Show success message
                        const successMsg = document.createElement('div');
                        successMsg.className = 'text-xs text-green-500 mt-1';
                        successMsg.textContent = 'Copied!';
                        
                        const container = document.getElementById('shareUrlContainer');
                        if (container) {
                          container.appendChild(successMsg);
                          setTimeout(() => {
                            container.removeChild(successMsg);
                          }, 2000);
                        }
                      })
                      .catch(err => console.error('Failed to copy:', err));
                  }}
                >
                  Copy
                </Button>
              </div>
              <div id="shareUrlContainer" className="h-5"></div>
            </div>
          )}
          
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="expirationPeriod">Expiration</Label>
              <Select 
                value={expirationPeriod} 
                onValueChange={handleExpirationPeriodChange}
              >
                <SelectTrigger id="expirationPeriod">
                  <SelectValue placeholder="Select expiration period" />
                </SelectTrigger>
                <SelectContent>
                  {EXPIRATION_PERIODS.map((period) => (
                    <SelectItem key={period.value} value={period.value}>
                      {period.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              {isCustomDate && (
                <div className="mt-2">
                  <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        className={cn(
                          "w-full justify-start text-left font-normal",
                          !expirationDate && "text-muted-foreground"
                        )}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {expirationDate ? format(expirationDate, "PPP") : "Pick a date"}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={expirationDate || undefined}
                        onSelect={(date) => {
                          if (date) {
                            setExpirationDate(date);
                            setCalendarOpen(false);
                          }
                        }}
                        disabled={(date) => date < new Date()}
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>
              )}
              
              {!isCustomDate && expirationDate && (
                <p className="text-sm text-muted-foreground mt-1">
                  Link expires on {format(expirationDate, "MMMM d, yyyy")}
                </p>
              )}
              {!isCustomDate && !expirationDate && expirationPeriod === "never" && (
                <p className="text-sm text-muted-foreground mt-1">
                  Link will never expire
                </p>
              )}
            </div>
            
            {/* Only show these options for Evaluations */}
            {resourceType === 'Evaluation' && (
              <>
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
              </>
            )}
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
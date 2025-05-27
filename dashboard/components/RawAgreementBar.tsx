import React from "react"
import { cn } from "@/lib/utils"

interface RawAgreementBarProps {
  agreements: number
  totalItems: number
  isFocused?: boolean
  isSelected?: boolean
}

export function RawAgreementBar({ 
  agreements, 
  totalItems,
  isFocused = false,
  isSelected = false
}: RawAgreementBarProps) {
  // Calculate percentages for bar display
  const agreedPercentage = totalItems > 0 ? (agreements / totalItems) * 100 : 0
  const disagreedPercentage = 100 - agreedPercentage
  
  // Ensure values are valid
  const clampedAgreedPercentage = Math.min(Math.max(agreedPercentage, 0), 100)
  const clampedDisagreedPercentage = Math.min(Math.max(disagreedPercentage, 0), 100)
  
  return (
    <div className={cn(
      "relative w-full h-8 rounded-md",
      isSelected ? "bg-progress-background-selected" : "bg-progress-background"
    )}>
      <div className="absolute top-0 left-0 h-full flex items-center pl-2 text-sm font-medium rounded-md text-primary-foreground">
        {agreements} / {totalItems}
      </div>
      
      {clampedAgreedPercentage > 0 && (
        <div
          className={cn(
            "absolute top-0 left-0 h-full flex items-center pl-2 text-sm font-medium",
            isSelected ? "bg-true-selected" : "bg-true",
            isFocused ? "text-focus" : isSelected ? "text-foreground-true" : "text-primary-foreground"
          )}
          style={{ 
            width: `${clampedAgreedPercentage}%`, 
            borderTopLeftRadius: 'inherit', 
            borderBottomLeftRadius: 'inherit',
            borderTopRightRadius: clampedDisagreedPercentage === 0 ? 'inherit' : 0,
            borderBottomRightRadius: clampedDisagreedPercentage === 0 ? 'inherit' : 0
          }}
        >
          {agreements} / {totalItems}
        </div>
      )}
      
      {clampedDisagreedPercentage > 0 && (
        <div
          className={cn(
            "absolute top-0 h-full",
            isSelected ? "bg-false-selected" : "bg-false"
          )}
          style={{ 
            left: `${clampedAgreedPercentage}%`, 
            width: `${clampedDisagreedPercentage}%`,
            borderTopLeftRadius: clampedAgreedPercentage === 0 ? 'inherit' : 0,
            borderBottomLeftRadius: clampedAgreedPercentage === 0 ? 'inherit' : 0,
            borderTopRightRadius: 'inherit',
            borderBottomRightRadius: 'inherit'
          }}
        />
      )}
    </div>
  )
} 
import React from "react"
import { cn } from "@/lib/utils"

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  variant?: 'primary' | 'secondary' | 'muted'
  className?: string
}

const sizeClasses = {
  sm: 'w-4 h-4 border-t-[2px]',
  md: 'w-6 h-6 border-t-[3px]', 
  lg: 'w-8 h-8 border-t-[4px]',
  xl: 'w-10 h-10 border-t-[8px]'
}

const variantClasses = {
  primary: 'border-primary',
  secondary: 'border-secondary', 
  muted: 'border-muted-foreground'
}

export function Spinner({ size = 'md', variant = 'secondary', className }: SpinnerProps) {
  return (
    <div 
      className={cn(
        'rounded-full animate-spin',
        sizeClasses[size],
        variantClasses[variant],
        className
      )}
    />
  )
}
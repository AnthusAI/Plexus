import React from 'react'
import { Button } from '@/components/ui/button'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface CardButtonProps {
  icon?: LucideIcon
  onClick: () => void
  disabled?: boolean
  'aria-label'?: string
  active?: boolean
  label?: string
  className?: string
  variant?: 'default' | 'primary' | 'secondary' | 'destructive'
  skeletonMode?: boolean
}

export function CardButton({
  icon: Icon,
  onClick,
  disabled,
  'aria-label': ariaLabel,
  active = false,
  label,
  className,
  variant = 'default',
  skeletonMode = false
}: CardButtonProps) {
  // Skeleton mode rendering
  if (skeletonMode) {
    return (
      <div 
        className={cn(
          label ? "h-10 w-20" : "h-8 w-8",
          "bg-muted rounded animate-pulse",
          className
        )}
      />
    );
  }

  const getVariantClasses = () => {
    switch (variant) {
      case 'primary':
        return 'bg-primary hover:bg-primary/90 text-primary-foreground'
      case 'secondary':
        return 'bg-secondary hover:bg-secondary/90 text-secondary-foreground'
      case 'destructive':
        return 'bg-destructive hover:bg-destructive/90 text-destructive-foreground'
      default:
        return active ? 'bg-accent' : 'bg-border'
    }
  }

  return (
    <Button
      variant="ghost"
      size={label ? "default" : "icon"}
      className={cn(
        label ? "gap-2" : Icon ? "h-8 w-8" : "",
        "rounded-md border-0 shadow-none",
        getVariantClasses(),
        className
      )}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
    >
      {Icon && <Icon className="h-4 w-4" />}
      {label && <span>{label}</span>}
    </Button>
  )
} 
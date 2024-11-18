import React from 'react'
import { Button } from '@/components/ui/button'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface CardButtonProps {
  icon: LucideIcon
  onClick?: () => void
  active?: boolean
  label?: string
}

export function CardButton({
  icon: Icon,
  onClick,
  active = false,
  label
}: CardButtonProps) {
  return (
    <Button
      variant="ghost"
      size={label ? "default" : "icon"}
      className={cn(
        label ? "gap-2" : "h-8 w-8",
        "rounded-md",
        active && "bg-accent"
      )}
      onClick={onClick}
    >
      <Icon className="h-4 w-4" />
      {label && <span>{label}</span>}
    </Button>
  )
} 
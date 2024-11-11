import React from 'react'
import { Button } from '@/components/ui/button'
import type { LucideIcon } from 'lucide-react'

export interface CardButtonProps {
  icon: LucideIcon
  label?: string
  onClick: () => void
}

export function CardButton({
  icon: Icon,
  onClick,
  label,
}: CardButtonProps) {
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    onClick()
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      className="px-3 h-9 bg-background hover:!bg-accent hover:!text-accent-foreground"
      onClick={handleClick}
    >
      <Icon className="h-4 w-4" />
      {label && <span className="ml-1.5 text-sm">{label}</span>}
    </Button>
  )
} 
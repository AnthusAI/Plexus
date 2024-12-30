import { Badge } from "@/components/ui/badge"
import { LucideIcon } from 'lucide-react'

type ScoreTypeBadgeProps = {
  icon: LucideIcon
  label: string
  subLabel: string
  color: string
}

export default function ScoreTypeBadge({ 
  icon: Icon, 
  label, 
  subLabel, 
  color 
}: ScoreTypeBadgeProps) {
  return (
    <div 
      className="flex flex-col justify-between h-full p-3 rounded-md"
      style={{ 
        backgroundColor: `hsl(var(--${color}-3))`,
      }}
    >
      <div className="flex items-center gap-2">
        <Icon 
          className="h-6 w-6 shrink-0"
          style={{ 
            color: `hsl(var(--${color}-11))`
          }}
        />
        <span className="text-sm font-medium text-foreground">
          {label}
        </span>
      </div>
      <div className="mt-2">
        <Badge variant="secondary">
          {subLabel}
        </Badge>
      </div>
    </div>
  )
} 
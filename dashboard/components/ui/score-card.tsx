import * as React from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { MoreHorizontal, X, Square, RectangleVertical, Save, X as Cancel } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Button } from '@/components/ui/button'

export interface ScoreData {
  id: string
  name: string
  key: string
  description: string
  type: string
  configuration: any
  order: number
}

interface ScoreCardProps extends React.HTMLAttributes<HTMLDivElement> {
  score: ScoreData
  variant?: 'grid' | 'detail'
  isSelected?: boolean
  onClick?: () => void
  onClose?: () => void
  onToggleFullWidth?: () => void
  isFullWidth?: boolean
  onSave?: (configuration: any) => Promise<void>
}

export function ScoreCard({
  score,
  variant = 'grid',
  isSelected,
  onClick,
  onClose,
  onToggleFullWidth,
  isFullWidth,
  onSave,
  className,
  ...props
}: ScoreCardProps) {
  const [editedConfig, setEditedConfig] = React.useState<string>('')
  const [isEditing, setIsEditing] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    // Reset edited config when score changes
    setEditedConfig(JSON.stringify(score.configuration, null, 2))
    setIsEditing(false)
    setError(null)
  }, [score])

  const handleEdit = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditedConfig(e.target.value)
    setIsEditing(true)
    setError(null)
  }

  const handleSave = async () => {
    try {
      const parsedConfig = JSON.parse(editedConfig)
      await onSave?.(parsedConfig)
      setIsEditing(false)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Invalid JSON format')
    }
  }

  const handleCancel = () => {
    setEditedConfig(JSON.stringify(score.configuration, null, 2))
    setIsEditing(false)
    setError(null)
  }

  if (variant === 'detail') {
    return (
      <Card
        className={cn(
          "w-full h-full flex flex-col overflow-hidden border-0",
          className
        )}
        {...props}
      >
        <div className="p-4 flex-1 flex flex-col min-h-0 w-full">
          <div className="flex justify-between items-start mb-6">
            <div className="space-y-2 flex-1">
              <h3 className="text-lg font-semibold">{score.name}</h3>
              <p className="text-sm text-muted-foreground">{score.description}</p>
              <div className="text-sm">
                <div><span className="font-medium">Key:</span> {score.key}</div>
                <div><span className="font-medium">Type:</span> {score.type}</div>
              </div>
            </div>
            <div className="flex gap-2">
              <CardButton
                icon={isFullWidth ? RectangleVertical : Square}
                onClick={() => onToggleFullWidth?.()}
                aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
              />
              <CardButton
                icon={X}
                onClick={() => onClose?.()}
                aria-label="Close"
              />
            </div>
          </div>
          <div className="flex-1 overflow-hidden w-full flex flex-col">
            <div className="flex-1 min-h-0 w-full relative bg-background rounded-lg p-1">
              <textarea
                className="w-full h-full absolute inset-0 font-mono text-sm p-4 resize-none bg-transparent border-0 focus:ring-0 focus:outline-none"
                value={editedConfig}
                onChange={handleEdit}
                spellCheck={false}
              />
            </div>
            {error && (
              <div className="text-sm text-destructive mt-2 px-1">
                {error}
              </div>
            )}
            {isEditing && (
              <div className="flex justify-end gap-2 mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCancel}
                  className="flex items-center gap-1"
                >
                  <Cancel className="h-4 w-4" />
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleSave}
                  className="flex items-center gap-1"
                >
                  <Save className="h-4 w-4" />
                  Save Changes
                </Button>
              </div>
            )}
          </div>
        </div>
      </Card>
    )
  }

  return (
    <Card
      className={cn(
        "w-full cursor-pointer hover:bg-accent/50 transition-colors",
        isSelected && "ring-2 ring-primary",
        className
      )}
      onClick={onClick}
      {...props}
    >
      <div className="p-4">
        <div className="space-y-2">
          <div className="text-sm">
            <div className="font-medium">{score.name}</div>
            <div className="text-muted-foreground">{score.description}</div>
          </div>
          <div className="text-sm text-muted-foreground">
            <div>Type: {score.type}</div>
            <div>Key: {score.key}</div>
          </div>
        </div>
      </div>
    </Card>
  )
} 
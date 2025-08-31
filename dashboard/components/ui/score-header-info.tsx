import * as React from 'react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export interface ScoreHeaderData {
  name: string
  description?: string
  key?: string
  externalId?: string
}

interface ScoreHeaderInfoProps {
  data: ScoreHeaderData
  onChange: (changes: Partial<ScoreHeaderData>) => void
  className?: string
  namePlaceholder?: string
  descriptionPlaceholder?: string
  keyPlaceholder?: string
  externalIdPlaceholder?: string
}

export function ScoreHeaderInfo({
  data,
  onChange,
  className,
  namePlaceholder = "Name",
  descriptionPlaceholder = "No description",
  keyPlaceholder = "key",
  externalIdPlaceholder = "External ID"
}: ScoreHeaderInfoProps) {
  const [containerRef, setContainerRef] = React.useState<HTMLDivElement | null>(null)
  const [isNarrow, setIsNarrow] = React.useState(false)

  // Use ResizeObserver to watch container width
  React.useEffect(() => {
    if (!containerRef) return

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        // Consider narrow if container width is less than 600px
        const narrow = entry.contentRect.width < 600
        setIsNarrow(narrow)
      }
    })

    resizeObserver.observe(containerRef)

    return () => {
      resizeObserver.disconnect()
    }
  }, [containerRef])

  const handleChange = (field: keyof ScoreHeaderData, value: string) => {
    onChange({ [field]: value })
  }

  if (isNarrow) {
    // Single column layout for narrow containers
    return (
      <div ref={setContainerRef} className={cn("space-y-3", className)}>
        {/* Name and Description group */}
        <div className="space-y-px">
          <Input
            value={data.name || ''}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
              handleChange('name', e.target.value)
            }
            className="text-base font-semibold bg-background border-0 px-3 py-2 h-auto w-full
                     placeholder:text-muted-foreground rounded-t-md rounded-b-none focus-visible:ring-2 focus-visible:z-10 relative"
            placeholder={namePlaceholder}
          />
          <textarea
            value={data.description || ''}
            onChange={(e) => handleChange('description', e.target.value)}
            placeholder={descriptionPlaceholder}
            className="w-full px-3 py-2 rounded-b-md rounded-t-none bg-background text-xs resize-none border-0 
                     placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:z-10 relative"
            rows={2}
          />
        </div>

        {/* Key and External ID group */}
        <div className="space-y-px">
          <Input
            value={data.key || ''}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
              handleChange('key', e.target.value)
            }
            className="font-mono bg-background border-0 px-3 py-2 h-auto w-full text-xs
                     placeholder:text-muted-foreground rounded-t-md rounded-b-none focus-visible:ring-2 focus-visible:z-10 relative"
            placeholder={keyPlaceholder}
          />
          <Input
            value={data.externalId || ''}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
              handleChange('externalId', e.target.value)
            }
            className="font-mono bg-background border-0 px-3 py-2 h-auto w-full
                     placeholder:text-muted-foreground rounded-b-md rounded-t-none focus-visible:ring-2 focus-visible:z-10 relative"
            placeholder={externalIdPlaceholder}
          />
        </div>
      </div>
    )
  }

  // Grid layout for wider containers - 2x2 grid
  return (
    <div ref={setContainerRef} className={cn("grid grid-cols-[1fr_auto] gap-px", className)}>
      {/* Top row: Name and Key */}
      <Input
        value={data.name || ''}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
          handleChange('name', e.target.value)
        }
        className="text-base font-semibold bg-background border-0 px-3 py-2 h-auto
                 placeholder:text-muted-foreground rounded-tl-md rounded-tr-none rounded-bl-none rounded-br-none focus-visible:ring-2 focus-visible:z-10 relative"
        placeholder={namePlaceholder}
      />
      <Input
        value={data.key || ''}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
          handleChange('key', e.target.value)
        }
        className="font-mono bg-background border-0 px-3 py-2 h-auto w-32 text-xs
                 placeholder:text-muted-foreground rounded-tl-none rounded-tr-md rounded-bl-none rounded-br-none focus-visible:ring-2 focus-visible:z-10 relative"
        placeholder={keyPlaceholder}
      />
      
      {/* Bottom row: Description and External ID */}
      <textarea
        value={data.description || ''}
        onChange={(e) => handleChange('description', e.target.value)}
        placeholder={descriptionPlaceholder}
        className="w-full px-3 py-2 rounded-tl-none rounded-tr-none rounded-bl-md rounded-br-none bg-background text-xs resize-none border-0 
                 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:z-10 relative"
        rows={2}
      />
      <Input
        value={data.externalId || ''}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
          handleChange('externalId', e.target.value)
        }
        className="font-mono bg-background border-0 px-3 py-2 h-auto w-32
                 placeholder:text-muted-foreground rounded-tl-none rounded-tr-none rounded-bl-none rounded-br-md focus-visible:ring-2 focus-visible:z-10 relative"
        placeholder={externalIdPlaceholder}
      />
    </div>
  )
}

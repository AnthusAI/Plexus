import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, Pencil, Database } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { ScoreCard, type ScoreData } from '@/components/ui/score-card'

export interface ScorecardDetailData {
  id: string
  title: string
  key: string
  externalId: string
  description: string
  sections: {
    items: Array<{
      id: string
      name: string
      order: number
      scores: {
        items: Array<{
          id: string
          name: string
          key: string
          description: string
          order: number
          type: string
          configuration: any
        }>
      }
    }>
  }
}

interface ScorecardDetailViewProps extends React.HTMLAttributes<HTMLDivElement> {
  data: ScorecardDetailData;
  onEdit?: () => void;
  onViewData?: () => void;
  onScoreSelect?: (score: any) => void;
  variant?: 'grid' | 'detail';
  isFullWidth?: boolean;
}

const GridContent = React.memo(({ 
  data,
  isSelected 
}: { 
  data: ScorecardDetailData
  isSelected?: boolean
}) => {
  return (
    <div className="space-y-2">
      <div className="text-sm">
        <div className="font-medium">{data.title}</div>
        <div className="text-muted-foreground">{data.description}</div>
      </div>
      <div className="text-sm text-muted-foreground">
        <div>Sections: {data.sections?.items?.length || 0}</div>
        <div>Total Scores: {data.sections?.items?.reduce((acc, section) => 
          acc + (section.scores?.items?.length || 0), 0
        ) || 0}</div>
      </div>
    </div>
  )
})

const DetailContent = React.memo(({ 
  data,
  isFullWidth,
  isSelected,
  onScoreSelect
}: { 
  data: ScorecardDetailData
  isFullWidth: boolean
  isSelected?: boolean
  onScoreSelect?: (score: any) => void
}) => {
  return (
    <div className="space-y-4 px-1">
      <div>
        <h3 className="text-lg font-semibold">{data.title}</h3>
        <p className="text-sm text-muted-foreground">{data.description}</p>
      </div>
      
      <div className="space-y-2">
        <div className="text-sm">
          <div><span className="font-medium">Key:</span> {data.key}</div>
          <div><span className="font-medium">External ID:</span> {data.externalId}</div>
        </div>
      </div>

      <div className="space-y-6">
        {data.sections?.items?.map(section => (
          <div key={section.id} className="space-y-2">
            <h4 className="font-medium text-sm text-muted-foreground">{section.name}</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {section.scores?.items?.map(score => (
                <ScoreCard
                  key={score.id}
                  score={score}
                  onClick={() => onScoreSelect?.(score)}
                  variant="grid"
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
})

export default function ScorecardDetailView({ 
  data, 
  onEdit, 
  onViewData, 
  onScoreSelect, 
  variant = 'grid', 
  isFullWidth,
  className, 
  ...props 
}: ScorecardDetailViewProps) {
  return (
    <Card
      className={cn(
        "w-full",
        className
      )}
      {...props}
    >
      <div className="flex justify-between items-start">
        <div className="flex-1">
          {variant === 'grid' ? (
            <GridContent data={data} />
          ) : (
            <DetailContent 
              data={data} 
              isFullWidth={isFullWidth || false}
              onScoreSelect={onScoreSelect}
            />
          )}
        </div>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger>
            <button
              type="button"
              className="inline-flex items-center justify-center h-8 w-8 rounded-md bg-border hover:bg-accent hover:text-accent-foreground"
              aria-label="Open menu"
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="end" className="min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
              {onEdit && (
                <DropdownMenu.Item 
                  className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                  onSelect={onEdit}
                >
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenu.Item>
              )}
              {onViewData && (
                <DropdownMenu.Item 
                  className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                  onSelect={onViewData}
                >
                  <Database className="mr-2 h-4 w-4" />
                  View Data
                </DropdownMenu.Item>
              )}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </Card>
  )
} 
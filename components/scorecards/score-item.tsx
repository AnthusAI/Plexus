"use client"
import { useState } from "react"
import { useRouter } from 'next/navigation'
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { 
  ChevronDown, 
  Search, 
  Pencil,
  Check,
  X 
} from "lucide-react"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { formatDistanceToNow } from "date-fns"
import MetricsGauges from "@/components/MetricsGauges"
import { EditableField } from "@/components/ui/editable-field"

interface ScoreItemProps {
  score: {
    id: string
    name: string
    type: string
    accuracy: number
    version: string
    timestamp: Date
    distribution: Array<{ category: string; value: number }>
    versionHistory: Array<{
      version: string
      parent: string | null
      timestamp: Date
      accuracy: number
      distribution: Array<{ category: string; value: number }>
    }>
    aiProvider?: string
    aiModel?: string
    isFineTuned?: boolean
  }
  scorecardId: string
  onEdit: (score: ScoreItemProps['score']) => void
}

// Add type for version
interface Version {
  accuracy: number
  distribution: Array<{ category: string; value: number }>
  // ... other version properties
}

// Add the GaugeConfig interface at the top with other interfaces
interface GaugeConfig {
  value: number
  label: string
}

// Update the getMetricsForVersion function with the proper type
function getMetricsForVersion(version: Version | null): GaugeConfig[] {
  if (!version) return []
  
  return [
    {
      value: version.accuracy,
      label: 'Accuracy'
    },
    ...(version.distribution?.map(d => ({
      value: d.value,
      label: d.category
    })) || [])
  ]
}

export function ScoreItem({ score, scorecardId, onEdit }: ScoreItemProps) {
  const router = useRouter()

  if (!score.versionHistory || score.versionHistory.length === 0) {
    const now = new Date()
    score.versionHistory = [
      {
        version: score.version,
        parent: null,
        timestamp: score.timestamp,
        accuracy: score.accuracy,
        distribution: score.distribution
      },
      {
        version: Date.now().toString(),
        parent: score.version,
        timestamp: new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000),
        accuracy: score.accuracy - 5,
        distribution: [
          { category: "Positive", value: score.accuracy - 5 },
          { category: "Negative", value: 105 - score.accuracy }
        ]
      },
      {
        version: (Date.now() - 1000).toString(),
        parent: null,
        timestamp: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000),
        accuracy: 0,
        distribution: []
      }
    ]
  }

  const latestVersion = score.versionHistory[0]
  const totalItems = latestVersion?.distribution?.reduce((sum, item) => sum + item.value, 0) ?? 0

  return (
    <div className="py-4 border-b last:border-b-0">
      <div className="flex justify-between items-start mb-1">
        <div className="flex flex-col">
          <EditableField
            value={score.name}
            onChange={(newName) => {
              onEdit({ ...score, name: newName })
            }}
            className="text-xl font-semibold" // H3 styling
          />
          <div className="text-xs text-muted-foreground mt-1 space-y-1">
            <div className="font-mono">LangGraphScore</div>
            <div className="flex flex-wrap gap-1">
              <Badge className="bg-muted-foreground text-muted">
                {score.aiProvider || 'OpenAI'}
              </Badge>
              <Badge className="bg-muted-foreground text-muted">
                {score.aiModel || 'gpt-4-mini'}
              </Badge>
              {score.isFineTuned && <Badge variant="secondary">Fine-tuned</Badge>}
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="text-xs"
            onClick={() => router.push(`/scorecards/${scorecardId}/scores/${score.id}/edit`)}
          >
            <Pencil className="h-4 w-4 mr-1" />
            Edit
          </Button>
        </div>
      </div>
      <div className="mt-4">
        <MetricsGauges gauges={getMetricsForVersion(latestVersion)} />
      </div>
      <Collapsible className="w-full mt-2">
        <CollapsibleTrigger className="flex items-center text-sm text-muted-foreground">
          <span>Version History</span>
          <ChevronDown className="h-4 w-4 ml-1" />
        </CollapsibleTrigger>
        <CollapsibleContent className="border-l-4 border-primary pl-4 mt-2">
          <div className="max-h-80 overflow-y-auto pr-4">
            <div className="space-y-4">
              {score.versionHistory.map((version, index) => (
                <div key={index} className="border-b last:border-b-0 pb-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="text-sm font-medium">
                        Version {version.version.substring(0, 7)}
                        {index === 0 && (
                          <span className="ml-2 text-xs bg-secondary text-secondary-foreground px-2 py-1 rounded-full">
                            Current
                          </span>
                        )}
                      </div>
                      {version.parent && (
                        <div className="text-xs text-muted-foreground">
                          Parent: <a href="#" className="text-primary hover:underline" onClick={(e) => {
                            e.preventDefault();
                            console.log(`Navigate to parent version: ${version.parent}`);
                          }}>{version.parent.substring(0, 7)}</a>
                        </div>
                      )}
                      <div className="text-xs text-muted-foreground">
                        {formatDistanceToNow(version.timestamp, { addSuffix: true })}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {index !== 0 && (
                        <Button variant="outline" size="sm">Use</Button>
                      )}
                      <Button variant="outline" size="sm">Edit</Button>
                    </div>
                  </div>
                  <div className="mt-4">
                    {getMetricsForVersion(version) ? (
                      <MetricsGauges gauges={getMetricsForVersion(version)!} />
                    ) : (
                      <div className="text-sm text-muted-foreground italic">
                        No metrics available for this version
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
} 
"use client"
import React, { useState, useEffect } from "react"
import { Button } from "./ui/button"
import { amplifyClient } from "@/utils/amplify-client"
import type { Schema } from "@/amplify/data/resource"
import type { AuthModeStrategyType } from "aws-amplify/datastore"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu"
import { 
  Activity, 
  Pencil, 
  MoreHorizontal,
  Plus,
  Database,
  RectangleVertical,
  Square,
  X
} from "lucide-react"
import { ScoreCount } from "./scorecards/score-count"
import { CardButton } from "./CardButton"
import { DatasetConfigFormComponent } from "./dataset-config-form"
import { listFromModel } from "@/utils/amplify-helpers"
import { AmplifyListResult } from '@/types/shared'
import { getClient } from "@/utils/amplify-client"
import { generateClient } from "aws-amplify/data"
import ScorecardComponent from "./scorecards/ScorecardComponent"
import { cn } from "@/lib/utils"
import { ScoreComponent } from "./ui/score-component"
import ScorecardDetailView from "./scorecards/ScorecardDetailView"

const ACCOUNT_KEY = 'call-criteria'

export default function ScorecardsComponent() {
  const [scorecards, setScorecards] = useState<Schema['Scorecard']['type'][]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedScorecard, setSelectedScorecard] = useState<Schema['Scorecard']['type'] | null>(null)
  const [selectedScore, setSelectedScore] = useState<{
    id: string
    name: string
    key: string
    description: string
    order: number
    type: string
    configuration: any
    sectionId: string
  } | null>(null)
  const [selectedScorecardSections, setSelectedScorecardSections] = useState<{
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
  } | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [showDatasetConfig, setShowDatasetConfig] = useState(false)
  const [selectedScorecardForDataset, setSelectedScorecardForDataset] = useState<string>("")
  const [leftPanelWidth, setLeftPanelWidth] = useState(40)
  const [scorecardScoreCounts, setScorecardScoreCounts] = useState<Record<string, number>>({})
  const [scorecardDetailWidth, setScorecardDetailWidth] = useState(50)
  const [maximizedScoreId, setMaximizedScoreId] = useState<string | null>(null)

  // Initial data load
  const fetchScorecards = async () => {
    try {
      const accountResult = await amplifyClient.Account.list({
        filter: { key: { eq: ACCOUNT_KEY } }
      })

      if (accountResult.data.length === 0) {
        setIsLoading(false)
        return
      }

      const foundAccountId = accountResult.data[0].id
      setAccountId(foundAccountId)

      const initialScorecards = await amplifyClient.Scorecard.list({
        filter: { accountId: { eq: foundAccountId } }
      })

      setScorecards(initialScorecards.data.filter(s => s.accountId === foundAccountId))
      setIsLoading(false)
    } catch (error) {
      console.error('Error loading initial data:', error)
      setError(error as Error)
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchScorecards()
  }, [])

  useEffect(() => {
    async function loadScorecardSections() {
      if (!selectedScorecard) {
        setSelectedScorecardSections(null)
        return
      }

      try {
        const sectionsResult = await selectedScorecard.sections()
        const sections = sectionsResult.data || []
        
        const transformedSections = {
          items: await Promise.all(sections.map(async section => {
            const scoresResult = await section.scores()
            const scores = scoresResult.data || []
            
            return {
              id: section.id,
              name: section.name,
              order: section.order,
              scores: {
                items: scores.map(score => ({
                  id: score.id,
                  name: score.name,
                  key: score.key || '',
                  description: score.description || '',
                  order: score.order,
                  type: score.type,
                  configuration: score.configuration
                }))
              }
            }
          }))
        }

        setSelectedScorecardSections(transformedSections)
      } catch (error) {
        console.error('Error loading scorecard sections:', error)
        setError(error as Error)
      }
    }

    loadScorecardSections()
  }, [selectedScorecard])

  // Helper function to fetch all scores for a section
  const fetchAllScoresForSection = async (sectionId: string) => {
    console.log('fetchAllScoresForSection: Starting to fetch all scores for section:', sectionId)
    let allScores: Schema['Score']['type'][] = []
    let nextToken: string | null = null
    
    do {
      const scoresResult = await amplifyClient.Score.list({
        filter: { sectionId: { eq: sectionId } },
        ...(nextToken ? { nextToken } : {})
      })
      console.log('fetchAllScoresForSection: Got page of scores:', scoresResult)
      allScores = [...allScores, ...(scoresResult.data || [])]
      nextToken = scoresResult.nextToken
    } while (nextToken)
    
    console.log('fetchAllScoresForSection: Total scores found:', allScores.length)
    return allScores
  }

  // Helper function to fetch sections with scores
  const fetchSectionsWithScores = async (scorecardId: string) => {
    const sectionsResult = await amplifyClient.ScorecardSection.list({
      filter: { scorecardId: { eq: scorecardId } }
    })
    
    const sortedSections = sectionsResult.data.sort((a, b) => a.order - b.order)
    
    return Promise.all(sortedSections.map(async (section) => ({
      id: section.id,
      name: section.name,
      order: section.order,
      scorecardId,
      createdAt: section.createdAt,
      updatedAt: section.updatedAt,
      scorecard: async () => amplifyClient.Scorecard.get({ id: scorecardId }),
      scores: async () => {
        const allScores = await fetchAllScoresForSection(section.id)
        return {
          data: allScores.sort((a, b) => a.order - b.order),
          nextToken: null
        }
      }
    })))
  }

  // Handle creating a new scorecard
  const handleCreate = async () => {
    if (!accountId) return

    const blankScorecard = {
      id: '',
      name: '',
      key: '',
      externalId: '',
      description: '',
      accountId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      account: async () => amplifyClient.Account.get({ id: accountId }),
      sections: async () => ({ 
        data: [],
        nextToken: null
      }),
      evaluations: async () => ({ data: [], nextToken: null }),
      batchJobs: async () => ({ data: [], nextToken: null }),
      item: async () => ({ data: null }),
      scoringJobs: async () => ({ data: [], nextToken: null }),
      scoreResults: async () => ({ data: [], nextToken: null }),
      actions: [],
      datasets: async () => ({ data: [], nextToken: null }),
      tasks: async (): Promise<AmplifyListResult<Schema['Task']['type']>> => {
        return listFromModel<Schema['Task']['type']>(
          client.models.Task,
          { scorecardId: { eq: '' } }
        );
      }
    } as Schema['Scorecard']['type']

    setSelectedScorecard(blankScorecard)
    setSelectedScorecardSections({ items: [] })
  }

  // Handle editing an existing scorecard
  const handleEdit = async (scorecard: Schema['Scorecard']['type']) => {
    try {
      console.log('handleEdit: Starting to edit scorecard:', scorecard.id)
      
      const fullScorecard = await amplifyClient.Scorecard.get({ id: scorecard.id })
      console.log('handleEdit: Full scorecard data:', fullScorecard.data)

      const scorecardData = fullScorecard.data
      if (!scorecardData) {
        throw new Error('Scorecard not found')
      }

      // Get all sections for this scorecard
      console.log('handleEdit: Fetching sections for scorecard:', scorecard.id)
      const sectionsResult = await amplifyClient.ScorecardSection.list({
        filter: { scorecardId: { eq: scorecard.id } }
      })
      console.log('handleEdit: Sections result:', sectionsResult)
      
      const sortedSections = sectionsResult.data.sort((a, b) => a.order - b.order)
      console.log('handleEdit: Sorted sections:', sortedSections)

      // Get scores for each section
      console.log('handleEdit: Starting to fetch scores for each section')
      const sectionsWithScores = await Promise.all(sortedSections.map(async section => {
        console.log('handleEdit: Fetching scores for section:', section.id)
        const allScores = await fetchAllScoresForSection(section.id)
        console.log('handleEdit: All scores for section:', section.id, allScores)
        return {
          ...section,
          scores: async () => ({
            data: allScores.sort((a, b) => a.order - b.order),
            nextToken: null
          })
        }
      }))
      console.log('handleEdit: All sections with scores:', sectionsWithScores)

      const accountResult = await amplifyClient.Account.get({ 
        id: scorecardData.accountId 
      })
      if (!accountResult.data) {
        throw new Error('Account not found')
      }
      
      const fullScorecardData = {
        ...scorecardData,
        account: async () => amplifyClient.Account.get({ id: scorecardData.accountId }),
        sections: async () => ({
          data: sectionsWithScores,
          nextToken: null
        }),
        evaluations: async () => amplifyClient.Evaluation.list({
          filter: { scorecardId: { eq: scorecardData.id } }
        }),
        batchJobs: async () => amplifyClient.BatchJob.list({
          filter: { scorecardId: { eq: scorecardData.id } }
        }),
        item: async () => scorecardData.itemId ? 
          amplifyClient.Item.get({ id: scorecardData.itemId }) :
          Promise.resolve({ data: null }),
        scoringJobs: async () => amplifyClient.ScoringJob.list({
          filter: { scorecardId: { eq: scorecardData.id } }
        }),
        scoreResults: async () => amplifyClient.ScoreResult.list({
          filter: { scorecardId: { eq: scorecardData.id } }
        }),
        actions: [],
        tasks: async (): Promise<AmplifyListResult<Schema['Task']['type']>> => {
          return listFromModel<Schema['Task']['type']>(
            client.models.Task,
            { scorecardId: { eq: scorecardData.id } }
          );
        }
      } as Schema['Scorecard']['type']
      
      console.log('Setting selected scorecard with data:', fullScorecardData)
      setSelectedScorecard(fullScorecardData)
    } catch (error) {
      console.error('Error fetching scorecard details:', error)
    }
  }

  const handleScoreSelect = (score: any, sectionId: string) => {
    setSelectedScore({ ...score, sectionId })
  }

  const renderSelectedScorecard = () => {
    if (!selectedScorecard || !selectedScorecardSections) return null;

    const scorecardData = {
      id: selectedScorecard.id,
      name: selectedScorecard.name,
      key: selectedScorecard.key || '',
      description: selectedScorecard.description || '',
      type: 'scorecard',
      configuration: {},
      order: 0,
      externalId: selectedScorecard.externalId || '',
      sections: selectedScorecardSections || { items: [] }
    }

    return (
      <div className={cn(
        "h-full overflow-y-auto overflow-x-hidden",
        maximizedScoreId ? "hidden" : ""
      )}
      style={selectedScore && !maximizedScoreId ? {
        width: `${scorecardDetailWidth}%`
      } : { width: '100%' }}>
        <ScorecardComponent
          variant="detail"
          score={scorecardData}
          onEdit={() => handleEdit(selectedScorecard)}
          onViewData={() => {
            setSelectedScorecardForDataset(selectedScorecard.id)
            setShowDatasetConfig(true)
          }}
          isFullWidth={isFullWidth}
          onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
          onClose={() => {
            setSelectedScorecard(null)
            setSelectedScore(null)
            setIsFullWidth(false)
          }}
          onSave={async () => {
            await fetchScorecards()
          }}
          onScoreSelect={handleScoreSelect}
        />
      </div>
    );
  };

  const renderSelectedScore = () => {
    if (!selectedScore) return null;

    return (
      <div className={cn(
        "h-full overflow-y-auto overflow-x-hidden",
        maximizedScoreId ? "w-full" : ""
      )}
      style={!maximizedScoreId ? {
        width: `${100 - scorecardDetailWidth}%`
      } : undefined}>
        <ScoreComponent
          score={selectedScore}
          variant="detail"
          isFullWidth={maximizedScoreId === selectedScore.id}
          onToggleFullWidth={() => setMaximizedScoreId(maximizedScoreId ? null : selectedScore.id)}
          onClose={() => {
            setSelectedScore(null);
            setMaximizedScoreId(null);
          }}
          onSave={async (configuration) => {
            // ... existing save logic ...
          }}
        />
      </div>
    );
  };

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.pageX
    const startWidth = leftPanelWidth

    const handleDrag = (e: MouseEvent) => {
      const delta = e.pageX - startX
      const newWidth = Math.min(Math.max(startWidth + (delta / window.innerWidth) * 100, 30), 70)
      setLeftPanelWidth(newWidth)
    }

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleDragEnd)
    }

    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleDragEnd)
  }

  useEffect(() => {
    async function calculateScoreCounts() {
      const counts: Record<string, number> = {}
      
      for (const scorecard of scorecards) {
        try {
          const sectionsResult = await scorecard.sections()
          const sections = sectionsResult.data || []
          
          let totalScores = 0
          for (const section of sections) {
            const scoresResult = await section.scores()
            totalScores += scoresResult.data?.length || 0
          }
          
          counts[scorecard.id] = totalScores
        } catch (error) {
          console.error('Error calculating score count:', error)
          counts[scorecard.id] = 0
        }
      }
      
      setScorecardScoreCounts(counts)
    }

    calculateScoreCounts()
  }, [scorecards])

  if (isLoading) {
    return <div>Loading scorecards...</div>
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="text-red-500 mb-2">
          Error loading scorecards: {error.message}
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex h-full w-full">
        {/* Grid Panel */}
        <div 
          className={cn(
            "h-full overflow-y-auto overflow-x-hidden",
            selectedScore || (selectedScorecard && isFullWidth) ? "hidden" : selectedScorecard ? "flex" : "w-full",
            "transition-all duration-200"
          )}
          style={selectedScorecard && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}
        >
          <div className="space-y-2 p-1.5 w-full">
            <div className="flex justify-end">
              <Button 
                onClick={handleCreate} 
                variant="ghost" 
                className="bg-card hover:bg-accent text-muted-foreground"
              >
                New Scorecard
              </Button>
            </div>
            <div className="@container">
              <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-4">
                {scorecards
                  .sort((a, b) => a.name.localeCompare(b.name))
                  .map(scorecard => {
                    const scorecardData = {
                      id: scorecard.id,
                      name: scorecard.name,
                      key: scorecard.key || '',
                      description: scorecard.description || '',
                      type: 'scorecard',
                      configuration: {},
                      order: 0,
                      externalId: scorecard.externalId || '',
                      scoreCount: scorecardScoreCounts[scorecard.id] || 0
                    }

                    return (
                      <ScorecardComponent
                        key={scorecard.id}
                        variant="grid"
                        score={scorecardData}
                        isSelected={selectedScorecard?.id === scorecard.id}
                        onClick={() => {
                          setSelectedScorecard(scorecard)
                          setSelectedScore(null)
                        }}
                        onEdit={() => handleEdit(scorecard)}
                      />
                    )
                  })}
              </div>
            </div>
          </div>
        </div>

        {/* Resize Handle between Grid and Detail */}
        {selectedScorecard && !isFullWidth && !selectedScore && (
          <div
            className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
            onMouseDown={handleDragStart}
          >
            <div className="absolute inset-0 rounded-full transition-colors duration-150 
              group-hover:bg-accent" />
          </div>
        )}

        {/* Detail Panel Container */}
        <div className="flex-1 flex overflow-hidden">
          {renderSelectedScorecard()}
          
          {/* Resize Handle between Scorecard and Score */}
          {selectedScore && !maximizedScoreId && (
            <div
              className="w-[12px] relative cursor-col-resize flex-shrink-0 group mx-1"
              onMouseDown={(e: React.MouseEvent<HTMLDivElement>) => {
                e.preventDefault()
                const startX = e.pageX
                const startDetailWidth = scorecardDetailWidth
                const container = e.currentTarget.parentElement
                if (!container) return

                const handleDrag = (e: MouseEvent) => {
                  const deltaX = e.pageX - startX
                  const containerWidth = container.getBoundingClientRect().width
                  const deltaPercent = (deltaX / containerWidth) * 100
                  const newDetailWidth = Math.min(Math.max(startDetailWidth + deltaPercent, 30), 70)
                  requestAnimationFrame(() => {
                    setScorecardDetailWidth(newDetailWidth)
                  })
                }

                const handleDragEnd = () => {
                  document.removeEventListener('mousemove', handleDrag)
                  document.removeEventListener('mouseup', handleDragEnd)
                  document.body.style.cursor = ''
                }

                document.body.style.cursor = 'col-resize'
                document.addEventListener('mousemove', handleDrag)
                document.addEventListener('mouseup', handleDragEnd)
              }}
            >
              <div className="absolute inset-0 rounded-full transition-colors duration-150 
                group-hover:bg-accent" />
            </div>
          )}
          
          {renderSelectedScore()}
        </div>
      </div>

      {showDatasetConfig && selectedScorecardForDataset && (
        <DatasetConfigFormComponent
          scorecardId={selectedScorecardForDataset}
          onClose={() => {
            setShowDatasetConfig(false)
            setSelectedScorecardForDataset("")
          }}
        />
      )}
    </div>
  )
}


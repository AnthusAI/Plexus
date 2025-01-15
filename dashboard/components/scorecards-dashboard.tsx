"use client"
import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { ScorecardForm } from "@/components/scorecards/create-edit-form"
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
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { 
  Activity, 
  Pencil, 
  MoreHorizontal,
  Plus,
  Database
} from "lucide-react"
import { ScoreCount } from "./scorecards/score-count"
import { CardButton } from "@/components/CardButton"
import { DatasetConfigFormComponent } from "@/components/dataset-config-form"
import { listFromModel } from "@/utils/amplify-helpers"
import { AmplifyListResult } from '@/types/shared'
import { getClient } from "@/utils/data-operations"
import { generateClient } from "aws-amplify/data"

const ACCOUNT_KEY = 'call-criteria'

const client = generateClient<Schema>()

export default function ScorecardsComponent() {
  const [scorecards, setScorecards] = useState<Schema['Scorecard']['type'][]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedScorecard, setSelectedScorecard] = useState<Schema['Scorecard']['type'] | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  
  // **Add refreshTrigger state (if needed)**
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  // Add missing state variables
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [showDatasetConfig, setShowDatasetConfig] = useState(false)
  const [selectedScorecardForDataset, setSelectedScorecardForDataset] = useState<string>("")

  useEffect(() => {
    let subscription: { unsubscribe: () => void } | null = null

    async function setupRealTimeSync() {
      try {
        const [accountResult, initialScorecards] = await Promise.all([
          amplifyClient.Account.list({
            filter: { key: { eq: ACCOUNT_KEY } }
          }),
          amplifyClient.Scorecard.list()
        ])

        if (accountResult.data.length > 0) {
          const foundAccountId = accountResult.data[0].id
          setAccountId(foundAccountId)
          
          setScorecards(initialScorecards.data.filter(s => 
            s.accountId === foundAccountId
          ))
          setIsLoading(false)

          subscription = amplifyClient.Scorecard.observeQuery({
            filter: { accountId: { eq: foundAccountId } }
          }).subscribe({
            next: ({ items }: { items: Schema['Scorecard']['type'][] }) => {
              console.log('Subscription event:', JSON.stringify(items, null, 2))
              setScorecards(items.filter((item: Schema['Scorecard']['type']) => 
                item && item.accountId === foundAccountId
              ))
            },
            error: (error: Error) => {
              console.error('Subscription error:', error)
              setError(error)
            }
          })
        } else {
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error setting up real-time sync:', error)
        setError(error as Error)
        setIsLoading(false)
      }
    }

    setupRealTimeSync()

    return () => {
      if (subscription) {
        subscription.unsubscribe()
      }
    }
  }, [])

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

    const newScorecard = {
      name: '',
      key: '',
      externalId: '',
      description: '',
      accountId,
    }

    setSelectedScorecard({
      ...newScorecard,
      id: '',
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
      scoreResults: async () => ({ data: [], nextToken: null })
    } as Schema['Scorecard']['type'])
    setIsEditing(true)
  }

  // Handle editing an existing scorecard
  const handleEdit = async (scorecard: Schema['Scorecard']['type']) => {
    if (isEditing) {
      setIsEditing(false)
    }
    
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
        })
      } as Schema['Scorecard']['type']
      
      console.log('Setting selected scorecard with data:', fullScorecardData)
      setSelectedScorecard(fullScorecardData)
      setIsEditing(true)
    } catch (error) {
      console.error('Error fetching scorecard details:', error)
    }
  }

  if (isLoading) {
    return <div>Loading scorecards...</div>;
  }

  if (error) {
    return (
      <div className="p-4 text-red-500">
        Error loading scorecards: {error.message}
      </div>
    )
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className={`flex flex-col flex-grow overflow-hidden pb-2`}>
        {(selectedScorecard || showDatasetConfig) ? (
          <div className="flex-shrink-0 h-full overflow-hidden">
            {selectedScorecard && (
              <ScorecardForm
                scorecard={selectedScorecard}
                accountId={accountId!}
                onSave={async () => {
                  setIsEditing(false)
                  setSelectedScorecard(null)
                }}
                onCancel={() => {
                  setIsEditing(false)
                  setSelectedScorecard(null)
                }}
                isFullWidth={isFullWidth}
                onToggleWidth={() => setIsFullWidth(!isFullWidth)}
                isNarrowViewport={isNarrowViewport}
              />
            )}
            {showDatasetConfig && (
              <DatasetConfigFormComponent 
                scorecardId={selectedScorecardForDataset}
                onClose={() => setShowDatasetConfig(false)}
                isFullWidth={isFullWidth}
                onToggleWidth={() => setIsFullWidth(!isFullWidth)}
                isNarrowViewport={isNarrowViewport}
              />
            )}
          </div>
        ) : (
          <div className={`flex ${isNarrowViewport || isFullWidth ? 'flex-col' : 'space-x-6'} h-full overflow-hidden`}>
            <div className={`flex-1 @container overflow-auto`}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[70%]">Scorecard</TableHead>
                    <TableHead className="w-[20%] @[630px]:table-cell hidden text-right">Scores</TableHead>
                    <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {scorecards.map((scorecard) => (
                    <TableRow 
                      key={scorecard.id} 
                      onClick={() => handleEdit(scorecard)} 
                      className="cursor-pointer transition-colors duration-200 hover:bg-muted"
                    >
                      <TableCell className="w-[70%]">
                        <div>
                          {/* Narrow variant - visible below 630px */}
                          <div className="block @[630px]:hidden">
                            <div className="flex justify-between items-start mb-2">
                              <div>
                                <div className="font-medium">{scorecard.name}</div>
                                <div className="text-sm text-muted-foreground font-mono">
                                  {scorecard.externalId || 'No ID'} - {scorecard.key}
                                </div>
                                <div className="text-sm text-muted-foreground mt-1">
                                  <ScoreCount scorecard={scorecard} />
                                </div>
                              </div>
                              <div className="flex items-center">
                                <CardButton 
                                  icon={Pencil}
                                  onClick={() => handleEdit(scorecard)}
                                />
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <CardButton 
                                      icon={MoreHorizontal}
                                      onClick={() => {}}
                                    />
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem onClick={(e) => {
                                      e.stopPropagation()
                                      setSelectedScorecardForDataset(scorecard.id)
                                      setShowDatasetConfig(true)
                                    }}>
                                      <Database className="h-4 w-4 mr-2" /> Datasets
                                    </DropdownMenuItem>
                                    <DropdownMenuItem>
                                      <Activity className="h-4 w-4 mr-2" /> Activity
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </div>
                            </div>
                          </div>
                          {/* Wide variant - visible at 630px and above */}
                          <div className="hidden @[630px]:block">
                            <div className="font-medium">{scorecard.name}</div>
                            <div className="text-sm text-muted-foreground font-mono">
                              {scorecard.externalId || 'No ID'} - {scorecard.key}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="w-[20%] hidden @[630px]:table-cell text-right">
                        <ScoreCount scorecard={scorecard} />
                      </TableCell>
                      <TableCell className="w-[10%] hidden @[630px]:table-cell text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <CardButton 
                            icon={Pencil}
                            onClick={() => {
                              handleEdit(scorecard)
                            }}
                          />
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                              <Button 
                                variant="ghost" 
                                size="icon"
                                className="h-8 w-8 p-0"
                              >
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={(e) => {
                                e.stopPropagation()
                                setSelectedScorecardForDataset(scorecard.id)
                                setShowDatasetConfig(true)
                              }}>
                                <Database className="h-4 w-4 mr-2" /> Datasets
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={(e) => e.stopPropagation()}>
                                <Activity className="h-4 w-4 mr-2" /> Activity
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-4">
                <CardButton
                  icon={Plus}
                  label="Create Scorecard"
                  onClick={handleCreate}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}


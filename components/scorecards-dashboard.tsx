"use client"
import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { ScorecardForm } from "@/components/scorecards/create-edit-form"
import { generateClient } from "aws-amplify/data"
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
  Plus 
} from "lucide-react"
import { ScoreCount } from "./scorecards/score-count"

// Initialize client
const client = generateClient<Schema>()

const ACCOUNT_KEY = 'call-criteria'

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

  useEffect(() => {
    let subscription: { unsubscribe: () => void } | null = null

    async function setupRealTimeSync() {
      try {
        // Get the account ID and initial scorecards in parallel
        const [accountResult, initialScorecards] = await Promise.all([
          client.models.Account.list({
            filter: { key: { eq: ACCOUNT_KEY } }
          }),
          client.models.Scorecard.list()
        ])

        if (accountResult.data.length > 0) {
          const foundAccountId = accountResult.data[0].id
          setAccountId(foundAccountId)
          
          // Show initial data immediately
          setScorecards(initialScorecards.data.filter(s => s.accountId === foundAccountId))
          setIsLoading(false)

          // Set up real-time subscription for future updates
          subscription = client.models.Scorecard.observeQuery({
            filter: { accountId: { eq: foundAccountId } }
          }).subscribe({
            next: ({ items }) => {
              console.log('Received real-time scorecard update:', items)
              setScorecards(items)
            },
            error: (error) => {
              console.error('Subscription error:', error)
              setError(error as Error)
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

  // Helper function to fetch sections with scores
  const fetchSectionsWithScores = async (scorecardId: string) => {
    const sectionsResult = await client.models.ScorecardSection.list({
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
      scorecard: async () => ({
        data: await client.models.Scorecard.get({ id: scorecardId }).then(result => result.data)
      }),
      scores: async () => {
        const scoresResult = await client.models.Score.list({
          filter: { sectionId: { eq: section.id } }
        })
        return {
          data: scoresResult.data,
          nextToken: null
        }
      }
    })))
  }

  // Handle creating a new scorecard
  const handleCreate = async () => {
    if (!accountId) return

    const newScorecard: Schema['Scorecard']['type'] = {
      id: '',
      name: '',
      key: '',
      externalId: '',
      description: '',
      accountId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      experiments: async () => ({
        data: [],
        nextToken: null
      }),
      account: async () => ({
        data: {
          id: accountId,
          name: ACCOUNT_KEY,
          key: ACCOUNT_KEY,
          description: '',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          experiments: async () => ({
            data: [],
            nextToken: null
          }),
          scorecards: async () => ({
            data: [],
            nextToken: null
          })
        }
      }),
      sections: async () => ({
        data: [],
        nextToken: null
      })
    }
    setSelectedScorecard(newScorecard)
    setIsEditing(true)
  }

  // Handle editing an existing scorecard
  const handleEdit = async (scorecard: Schema['Scorecard']['type']) => {
    if (isEditing) {
      setIsEditing(false)
    }
    
    try {
      console.log('Editing scorecard:', scorecard.id)
      
      const fullScorecard = await client.models.Scorecard.get({ id: scorecard.id })
      console.log('Full scorecard data:', fullScorecard.data)

      const scorecardData = fullScorecard.data
      if (!scorecardData) {
        throw new Error('Scorecard not found')
      }

      // Get all sections for this scorecard
      const sectionsResult = await client.models.ScorecardSection.list({
        filter: { scorecardId: { eq: scorecard.id } }
      })
      console.log('Sections result:', sectionsResult)
      
      const sortedSections = sectionsResult.data.sort((a, b) => a.order - b.order)
      console.log('Sorted sections:', sortedSections)

      // Get scores for each section
      const sectionsWithScores = await Promise.all(sortedSections.map(async section => {
        const scoresResult = await client.models.Score.list({
          filter: { sectionId: { eq: section.id } }
        })
        console.log(`Scores for section ${section.id}:`, scoresResult.data)
        return {
          ...section,
          scores: async () => ({
            data: scoresResult.data.sort((a, b) => a.order - b.order),
            nextToken: null
          })
        }
      }))
      console.log('Sections with scores:', sectionsWithScores)

      const accountResult = await client.models.Account.get({ 
        id: scorecardData.accountId 
      })
      if (!accountResult.data) {
        throw new Error('Account not found')
      }
      const accountData = accountResult.data
      
      const fullScorecardData: Schema['Scorecard']['type'] = {
        ...scorecardData,
        experiments: async () => ({
          data: [],
          nextToken: null
        }),
        account: async () => ({
          data: {
            id: accountData.id,
            name: accountData.name!,
            key: accountData.key!,
            description: accountData.description ?? '',
            experiments: async () => ({
              data: [],
              nextToken: null
            }),
            scorecards: async () => ({
              data: await client.models.Scorecard.list({
                filter: { accountId: { eq: accountData.id } }
              }).then(result => result.data),
              nextToken: null
            }),
            createdAt: accountData.createdAt!,
            updatedAt: accountData.updatedAt!
          }
        }),
        sections: async () => ({
          data: sectionsWithScores,
          nextToken: null
        })
      }
      
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
        {selectedScorecard && (
          <div className="flex-shrink-0 h-full overflow-hidden">
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
          </div>
        )}
        
        <div className={`flex ${isNarrowViewport || isFullWidth ? 'flex-col' : 'space-x-6'} h-full overflow-hidden`}>
          <div className={`${isFullWidth && selectedScorecard ? 'hidden' : 'flex-1'} @container overflow-auto`}>
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
                              <Button 
                                variant="ghost" 
                                size="icon"
                                onClick={(e) => { e.stopPropagation(); handleEdit(scorecard); }}
                                className="h-8 w-8"
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button 
                                    variant="ghost" 
                                    size="icon"
                                    onClick={(e) => e.stopPropagation()}
                                    className="h-8 w-8"
                                  >
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem>
                                    <Activity className="h-4 w-4 mr-2" /> Activity
                                  </DropdownMenuItem>
                                  {/* Add other DropdownMenuItems here */}
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
                        <Button 
                          variant="ghost" 
                          size="icon"
                          onClick={(e) => { e.stopPropagation(); handleEdit(scorecard); }}
                          className="h-8 w-8 p-0"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={(e) => e.stopPropagation()}
                              className="h-8 w-8 p-0"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem>
                              <Activity className="h-4 w-4 mr-2" /> Activity
                            </DropdownMenuItem>
                            {/* Add other DropdownMenuItems here */}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="mt-4">
              <Button variant="outline" onClick={handleCreate}>
                <Plus className="mr-2 h-4 w-4" /> Create Scorecard
              </Button>
            </div>
          </div>

          {selectedScorecard && !isNarrowViewport && !isFullWidth && (
            <div className="flex-1 overflow-hidden">
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
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


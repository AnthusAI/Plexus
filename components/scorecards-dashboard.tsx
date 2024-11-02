"use client"
import React, { useState, useRef, useEffect, useMemo } from "react"
import { AudioLines, Siren, FileBarChart, FlaskConical, Zap, Plus, Pencil, Trash2, ArrowLeft, MoreHorizontal, Activity, ChevronDown, Square, Columns2, X, Search, Check, Info, ThumbsUp, ThumbsDown, MessageCircleMore } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { format, formatDistanceToNow } from "date-fns"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { PieChart, Pie, ResponsiveContainer, Cell } from "recharts"
import { Badge } from "@/components/ui/badge"
import Link from 'next/link'
import { useRouter } from 'next/navigation'  // Change this import
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { ScorecardForm } from "./scorecards/create-edit-form"
import { generateClient as generateGraphQLClient } from '@aws-amplify/api'
import { Amplify } from 'aws-amplify'

// Initialize both clients
const client = generateClient<Schema>()
const graphqlClient = generateGraphQLClient()

const ACCOUNT_KEY = 'call-criteria';

// Add this function near the top of the file, with other utility functions
const generateHexCode = (length: number = 7): string => {
  return Array.from({length}, () => Math.floor(Math.random() * 16).toString(16)).join('');
};

const initialScorecards: Scorecard[] = [
  { 
    id: "1329", 
    name: "SelectQuote Term Life v1", 
    key: "termlifev1", 
    scores: 12, 
    scoreDetails: [
      {
        name: "Technical",
        scores: [
          { 
            id: "1", 
            name: "Scoreable Call", 
            type: "Boolean",
            accuracy: 85,
            version: "a1b2c3d",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 85 },
              { category: "Negative", value: 15 }
            ],
            versionHistory: [],
            aiProvider: "OpenAI",
            aiModel: "gpt-4-turbo",
            isFineTuned: true  // This score is now fine-tuned
          },
          { 
            id: "2", 
            name: "Call Efficiency", 
            type: "Boolean",
            accuracy: 78,
            version: "e4f5g6h",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 78 },
              { category: "Negative", value: 22 }
            ],
            versionHistory: [],
            aiProvider: "Anthropic",
            aiModel: "claude-2",
            isFineTuned: false
          },
        ]
      },
      {
        name: "Sales",
        scores: [
          { 
            id: "3", 
            name: "Assumptive Close", 
            type: "Boolean",
            accuracy: 94,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "4", 
            name: "Problem Resolution", 
            type: "Boolean",
            accuracy: 92,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
        ]
      },
      {
        name: "Soft Skills",
        scores: [
          { 
            id: "5", 
            name: "Rapport", 
            type: "Boolean",
            accuracy: 94,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "6", 
            name: "Friendly Greeting", 
            type: "Boolean",
            accuracy: 89,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "7", 
            name: "Agent Offered Name", 
            type: "Boolean",
            accuracy: 98,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "8", 
            name: "Temperature Check", 
            type: "Boolean",
            accuracy: 91,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
        ]
      },
      {
        name: "Compliance",
        scores: [
          { 
            id: "9", 
            name: "DNC Requested", 
            type: "Boolean",
            accuracy: 98,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "10", 
            name: "Profanity", 
            type: "Boolean",
            accuracy: 99,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "11", 
            name: "Agent Offered Legal Advice", 
            type: "Boolean",
            accuracy: 97,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "12", 
            name: "Agent Offered Guarantees", 
            type: "Boolean",
            accuracy: 98,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
        ]
      }
    ]
  },
  { id: "1321", name: "CS3 Audigy TPA", key: "cs3_audigy_tpa", scores: 1, scoreDetails: [] },
  { id: "1372", name: "CS3 Services v2", key: "cs3_services_v2", scores: 1, scoreDetails: [] },
]

const scoreTypes = ["Numeric", "Percentage", "Boolean", "Text"]

// Define an interface for the scorecard structure
interface Scorecard {
  id: string;
  name: string;
  key: string;
  scores: number;
  scoreDetails: Array<{
    name: string;
    scores: Array<{
      id: string;
      name: string;
      type: string;
      accuracy: number;
      version: string;
      timestamp: Date;
      distribution: Array<{ category: string; value: number }>;
      versionHistory: Array<{
        version: string;
        parent: string | null;  // Add this line
        timestamp: Date;
        accuracy: number;
        distribution: Array<{ category: string; value: number }>;
      }>;
      aiProvider?: string;
      aiModel?: string;
      isFineTuned?: boolean;
    }>;
  }>;
}

type EditableFieldProps = {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  autoFocus?: boolean;
}

function EditableField({ value, onChange, className = "", autoFocus = false }: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(autoFocus)
  const [tempValue, setTempValue] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if ((isEditing || autoFocus) && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isEditing, autoFocus])

  const handleEditToggle = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsEditing((prev) => !prev);
    setTempValue(value);
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTempValue(e.target.value)
  }

  const handleSave = () => {
    onChange(tempValue)
    setIsEditing(false)
  }

  const handleCancel = () => {
    setTempValue(value)
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSave()
    } else if (e.key === 'Escape') {
      handleCancel()
    }
  }

  return (
    <div className="flex items-center space-x-2">
      {isEditing ? (
        <>
          <Input
            ref={inputRef}
            type="text"
            value={tempValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            className={`py-1 px-2 -ml-2 ${className}`}
          />
          <Button 
            variant="ghost" 
            size="icon"
            className="h-8 w-8 flex-shrink-0"
            onClick={handleSave}
          >
            <Check className="h-4 w-4" />
          </Button>
          <Button 
            variant="ghost" 
            size="icon"
            className="h-8 w-8 flex-shrink-0"
            onClick={handleCancel}
          >
            <X className="h-4 w-4" />
          </Button>
        </>
      ) : (
        <>
          <span 
            className={`cursor-pointer hover:bg-accent hover:text-accent-foreground py-1 px-2 -ml-2 rounded border border-transparent transition-colors duration-200 ${className}`}
          >
            {value}
          </span>
          <Button 
            variant="ghost" 
            size="icon"
            className="h-8 w-8 flex-shrink-0"
            onClick={handleEditToggle}
          >
            <Pencil className="h-4 w-4" />
          </Button>
        </>
      )}
    </div>
  )
}

// Add near the top of the file
interface ScoreSection {
  name: string;
  scores: Array<{
    id: string;
    name: string;
    type: string;
    accuracy: number;
    version: string;
    timestamp: Date;
    distribution: Array<{ category: string; value: number }>;
    versionHistory: Array<any>;
  }>;
}

// Remove the extends since we can't extend the Schema type directly
interface ParsedScorecard {
  id: string
  name: string
  key: string
  externalId: string
  description?: string
  accountId: string
  sections: Array<{
    id: string
    name: string
    order: number
    scores: Array<{
      id: string
      name: string
      type: string
      order: number
      accuracy: number
      version: string
      aiProvider?: string
      aiModel?: string
      isFineTuned?: boolean
      configuration?: any
      distribution?: any
      versionHistory?: any
    }>
  }>
  createdAt: string
  updatedAt: string
}

// Add this function to get the score count
const getScoreCountForScorecard = async (scorecard: Schema['Scorecard']['type']) => {
  try {
    console.log('Getting score count for scorecard:', scorecard)
    console.log('Data Store Client in getScoreCount:', client)
    console.log('Available models:', client.models)
    
    if (!client?.models?.Section) {
      console.error('Section model not available')
      return 0
    }

    const sectionsResult = await client.models.Section.list({
      filter: {
        scorecardId: {
          eq: scorecard.id
        }
      }
    })
    
    let count = 0
    for (const section of sectionsResult.data) {
      if (!client?.models?.Score) {
        console.error('Score model not available')
        continue
      }
      
      const scoresResult = await client.models.Score.list({
        filter: {
          sectionId: {
            eq: section.id
          }
        }
      })
      count += scoresResult.data.length
    }
    return count
  } catch (error) {
    console.error('Error getting score count:', error)
    return 0
  }
}

// Add type definitions for distribution and version history items
interface DistributionItem {
  category: string
  value: number
}

interface VersionHistoryItem {
  version: string
  parent: string | null
  timestamp: Date
  accuracy: number
  distribution: DistributionItem[]
}

// Add this component near the top with other component definitions
const ScoreCount = ({ scorecard }: { scorecard: Schema['Scorecard']['type'] }) => {
  const [count, setCount] = useState(0)
  
  useEffect(() => {
    getScoreCountForScorecard(scorecard).then(setCount)
  }, [scorecard])
  
  return <>{count} scores</>
}

export default function ScorecardsComponent() {
  const router = useRouter()
  const [scorecards, setScorecards] = useState<Schema['Scorecard']['type'][]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedScorecard, setSelectedScorecard] = useState<ParsedScorecard | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editingScore, setEditingScore] = useState<{ id: string; name: string; type: string } | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [editingName, setEditingName] = useState(false)
  const [isDetailViewFresh, setIsDetailViewFresh] = useState(true)
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [accountId, setAccountId] = useState<string | null>(null)

  // Move useEffect to the top level
  useEffect(() => {
    if (isDetailViewFresh && selectedScorecard) {
      setIsDetailViewFresh(false);
    }
  }, [isDetailViewFresh, selectedScorecard]);

  useEffect(() => {
    console.log('Fetching scorecards...')
    fetchScorecards()
  }, [refreshTrigger])

  const fetchScorecards = async () => {
    try {
      setIsLoading(true)
      
      // Get account first
      const accountResult = await client.models.Account.list({
        filter: {
          key: {
            eq: ACCOUNT_KEY
          }
        }
      })
      
      if (accountResult.data.length > 0) {
        const foundAccountId = accountResult.data[0].id
        setAccountId(foundAccountId)
        
        // Use GraphQL query since it works
        const query = /* GraphQL */ `
          query ListScorecards {
            listScorecards {
              items {
                id
                name
                key
                externalId
                accountId
                description
                createdAt
                updatedAt
              }
            }
          }
        `
        
        const result = await graphqlClient.graphql({ query })
        const typedResult = result as {
          data: {
            listScorecards: {
              items: Schema['Scorecard']['type'][]
            }
          }
        }
        
        console.log('GraphQL result:', JSON.stringify(typedResult, null, 2))
        
        if (typedResult.data?.listScorecards?.items) {
          setScorecards(typedResult.data.listScorecards.items)
        } else {
          setScorecards([])
        }
      }
    } catch (error) {
      console.error('Error fetching scorecards:', error)
      setScorecards([])
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return <div>Loading scorecards...</div>;
  }

  const handleCreate = () => {
    if (!accountId) return

    const newScorecard: ParsedScorecard = {
      id: '',
      name: '',
      key: '',
      externalId: '',
      description: '',
      accountId,
      sections: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }
    setSelectedScorecard(newScorecard)
    setIsEditing(true)
    setEditingScore(null)
    setIsDetailViewFresh(true)
  }

  const handleEdit = async (scorecard: Schema['Scorecard']['type']) => {
    if (isEditing) {
      setIsEditing(false)
    }
    
    try {
      // Fetch sections using Data Store
      const sectionsResult = await client.models.Section.list({
        filter: {
          scorecardId: {
            eq: scorecard.id
          }
        }
      })
      
      // For each section, fetch its scores
      const sections = await Promise.all(
        sectionsResult.data.map(async (section) => {
          const scoresResult = await client.models.Score.list({
            filter: {
              sectionId: {
                eq: section.id
              }
            }
          })
          
          return {
            id: section.id,
            name: section.name,
            order: section.order,
            scores: scoresResult.data.map(score => ({
              id: score.id,
              name: score.name,
              type: score.type,
              order: score.order,
              accuracy: score.accuracy ?? 0,
              version: score.version ?? '',
              aiProvider: score.aiProvider ?? undefined,
              aiModel: score.aiModel ?? undefined,
              isFineTuned: score.isFineTuned ?? false,
              configuration: score.configuration ?? undefined,
              distribution: score.distribution ?? undefined,
              versionHistory: score.versionHistory ?? undefined
            }))
          }
        })
      )
      
      const parsedScorecard: ParsedScorecard = {
        id: scorecard.id,
        name: scorecard.name,
        key: scorecard.key,
        externalId: scorecard.externalId,
        description: scorecard.description ?? undefined,
        accountId: scorecard.accountId,
        sections,
        createdAt: scorecard.createdAt,
        updatedAt: scorecard.updatedAt
      }
      
      setSelectedScorecard(parsedScorecard)
      setIsEditing(true)
      setEditingScore(null)
      setIsDetailViewFresh(true)
    } catch (error) {
      console.error('Error fetching sections:', error)
    }
  }

  const handleDelete = (id: string) => {
    setScorecards(scorecards.filter(scorecard => scorecard.id !== id))
    if (selectedScorecard && selectedScorecard.id === id) {
      setSelectedScorecard(null)
      setIsEditing(false)
    }
  }

  const handleSave = async () => {
    if (!selectedScorecard || !accountId) return
    
    try {
      if (!selectedScorecard.id) {
        // Create new scorecard
        const scorecardResult = await client.models.Scorecard.create({
          name: selectedScorecard.name,
          key: selectedScorecard.key,
          externalId: selectedScorecard.externalId,
          description: selectedScorecard.description,
          accountId: selectedScorecard.accountId
        })
        
        if (!scorecardResult.data) {
          throw new Error('Failed to create scorecard')
        }
        
        // Create sections
        for (const section of selectedScorecard.sections) {
          const sectionResult = await client.models.Section.create({
            name: section.name,
            order: section.order,
            scorecardId: scorecardResult.data.id
          })
          
          if (!sectionResult.data) {
            throw new Error('Failed to create section')
          }
          
          // Create scores
          for (const score of section.scores) {
            await client.models.Score.create({
              name: score.name,
              type: score.type,
              order: score.order,
              sectionId: sectionResult.data.id,
              accuracy: score.accuracy,
              version: score.version,
              aiProvider: score.aiProvider,
              aiModel: score.aiModel,
              isFineTuned: score.isFineTuned,
              configuration: score.configuration,
              distribution: score.distribution,
              versionHistory: score.versionHistory
            })
          }
        }
      } else {
        // Update existing scorecard
        await client.models.Scorecard.update({
          id: selectedScorecard.id,
          name: selectedScorecard.name,
          key: selectedScorecard.key,
          externalId: selectedScorecard.externalId,
          description: selectedScorecard.description
        })
        
        // Update sections
        for (const section of selectedScorecard.sections) {
          if (section.id) {
            await client.models.Section.update({
              id: section.id,
              name: section.name,
              order: section.order
            })
          } else {
            await client.models.Section.create({
              name: section.name,
              order: section.order,
              scorecardId: selectedScorecard.id
            })
          }
        }
      }
      
      setIsEditing(false)
      setRefreshTrigger(prev => prev + 1)
    } catch (error) {
      console.error('Error saving scorecard:', error)
    }
  }

  const handleCancel = () => {
    setSelectedScorecard(null)
    setIsEditing(false)
    setEditingScore(null)
  }

  const handleAddScore = async (sectionIndex: number) => {
    if (!selectedScorecard) return
    
    const section = selectedScorecard.sections[sectionIndex]
    const maxOrder = Math.max(0, ...section.scores.map(s => s.order))
    
    const newScore = {
      id: '',
      name: "New Score",
      type: "LangGraphScore",
      order: maxOrder + 1,
      accuracy: 0,
      version: Date.now().toString(),
      aiProvider: "OpenAI",
      aiModel: "gpt-4",
      isFineTuned: false,
      configuration: {},
      distribution: [],
      versionHistory: []
    }
    
    const updatedSections = [...selectedScorecard.sections]
    updatedSections[sectionIndex] = {
      ...section,
      scores: [...section.scores, newScore]
    }
    
    setSelectedScorecard({
      ...selectedScorecard,
      sections: updatedSections
    })
  }

  const handleSaveScore = () => {
    if (!selectedScorecard || !editingScore) return
    
    const newScore = {
      id: editingScore.id || '',
      name: editingScore.name,
      type: editingScore.type,
      order: 0, // Will be set properly when saving
      accuracy: 0,
      version: Date.now().toString(),
      aiProvider: "OpenAI",
      aiModel: "gpt-4",
      isFineTuned: false,
      configuration: {},
      distribution: [],
      versionHistory: []
    }

    const updatedSections = selectedScorecard.sections.map(section => ({
      ...section,
      scores: editingScore.id 
        ? section.scores.map(score => score.id === editingScore.id ? newScore : score)
        : [...section.scores, newScore]
    }))

    setSelectedScorecard({
      ...selectedScorecard,
      sections: updatedSections
    })
    setEditingScore(null)
  }

  const handleDeleteScore = (scoreId: string) => {
    if (!selectedScorecard) return

    const updatedSections = selectedScorecard.sections.map(section => ({
      ...section,
      scores: section.scores.filter(score => score.id !== scoreId)
    }))

    setSelectedScorecard({
      ...selectedScorecard,
      sections: updatedSections
    })
  }

  const handleNameEdit = () => {
    setEditingName(true)
  }

  const handleNameSave = (newName: string) => {
    if (selectedScorecard) {
      setSelectedScorecard({ ...selectedScorecard, name: newName })
      setEditingName(false)
    }
  }

  const handleEditScore = (scorecardId: string, scoreId: string) => {
    router.push(`/scorecards/${scorecardId}/scores/${scoreId}/edit`)
  }

  const renderScorecardsTable = () => (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[70%]">Scorecard</TableHead>
            <TableHead className="w-[20%] text-right">Scores</TableHead>
            <TableHead className="w-[10%] text-right">Actions</TableHead>
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
                  <div className="font-medium">{scorecard.name}</div>
                  <div className="text-sm text-muted-foreground font-mono">
                    {scorecard.externalId || 'No ID'} - {scorecard.key}
                  </div>
                </div>
              </TableCell>
              <TableCell className="w-[20%] text-right">
                {useMemo(() => {
                  const [count, setCount] = useState(0)
                  useEffect(() => {
                    getScoreCountForScorecard(scorecard).then(setCount)
                  }, [scorecard])
                  return count
                }, [scorecard])}
              </TableCell>
              <TableCell className="w-[10%]">
                <div className="flex items-center justify-end space-x-2">
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={(e) => { e.stopPropagation(); handleEdit(scorecard); }}
                    className="h-8 w-8 p-0"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button 
                        variant="ghost" 
                        size="sm"
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
                      <DropdownMenuItem>
                        <AudioLines className="h-4 w-4 mr-2" /> Items
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Siren className="h-4 w-4 mr-2" /> Alerts
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <FileBarChart className="h-4 w-4 mr-2" /> Reports
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <FlaskConical className="h-4 w-4 mr-2" /> Experiments
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Zap className="h-4 w-4 mr-2" /> Optimizations
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
        <Button variant="outline" onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" /> Create Scorecard
        </Button>
      </div>
    </div>
  )

  const renderSelectedItem = () => {
    if (isEditing) {
      if (!accountId) {
        return <div>Loading account information...</div>
      }
      
      const formScorecard = selectedScorecard ? {
        id: selectedScorecard.id,
        name: selectedScorecard.name,
        key: selectedScorecard.key,
        externalId: selectedScorecard.externalId,
        description: selectedScorecard.description,
        accountId: selectedScorecard.accountId,
        createdAt: selectedScorecard.createdAt,
        updatedAt: selectedScorecard.updatedAt,
        account: {
          get: async () => {
            const result = await client.models.Account.get({ 
              id: accountId
            })
            return result.data
          }
        } as any,
        sections: {
          get: async () => {
            const result = await client.models.Section.list({
              filter: {
                scorecardId: { eq: selectedScorecard.id }
              }
            })
            return result.data
          }
        } as any
      } : null
      
      return (
        <ScorecardForm
          scorecard={formScorecard as Schema['Scorecard']['type']}
          accountId={accountId}
          onSave={() => {
            setIsEditing(false)
            setSelectedScorecard(null)
            setRefreshTrigger(prev => prev + 1)
          }}
          onCancel={() => {
            setIsEditing(false)
            setSelectedScorecard(null)
          }}
          isFullWidth={isFullWidth}
          onToggleWidth={() => setIsFullWidth(!isFullWidth)}
          isNarrowViewport={isNarrowViewport}
        />
      )
    }

    if (!selectedScorecard) {
      return <div>No scorecard selected</div>
    }

    if (!selectedScorecard.sections || selectedScorecard.sections.length === 0) {
      return <div>No sections configured yet</div>
    }

    const renderScoreItem = (score: ParsedScorecard['sections'][0]['scores'][0], sectionId: string) => {
      const latestVersion = score.versionHistory?.[0] ?? {
        version: score.version,
        accuracy: score.accuracy,
        distribution: score.distribution ?? [
          { category: "Positive", value: score.accuracy },
          { category: "Negative", value: 100 - score.accuracy }
        ]
      }

      const totalItems = latestVersion.distribution?.reduce((sum: number, item: DistributionItem) => 
        sum + item.value, 0) ?? 0

      return (
        <div key={score.id} className="py-4 border-b last:border-b-0">
          <div className="flex justify-between items-start mb-1">
            <div className="flex flex-col">
              <h5 className="text-sm font-medium">{score.name}</h5>
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
                onClick={() => handleEditScore(selectedScorecard.id, score.id)}
              >
                <Pencil className="h-4 w-4 mr-1" />
                Edit
              </Button>
            </div>
          </div>
          <div className="flex items-center justify-end mt-2">
            <div className="text-right mr-4">
              <div className="text-lg font-bold">
                {latestVersion.accuracy}% / {totalItems}
              </div>
              <div className="text-sm text-muted-foreground">
                Accuracy
              </div>
            </div>
            <div className="w-[80px] h-[80px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={latestVersion.distribution}
                    dataKey="value"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    innerRadius={0}
                    outerRadius={30}
                    fill="var(--true)"
                    strokeWidth={0}
                  >
                    {latestVersion.distribution.map((entry: DistributionItem, index: number) => (
                      <Cell key={`cell-${index}`} fill={index === 0 ? "var(--true)" : "var(--false)"} />
                    ))}
                  </Pie>
                  <Pie
                    data={[
                      { category: "Positive", value: 50 },
                      { category: "Negative", value: 50 },
                    ]}
                    dataKey="value"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    innerRadius={35}
                    outerRadius={40}
                    fill="var(--chart-2)"
                    strokeWidth={0}
                  >
                    {[0, 1].map((_, index) => (
                      <Cell key={`cell-${index}`} fill={index === 0 ? "var(--true)" : "var(--false)"} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <Collapsible className="w-full mt-2">
            <CollapsibleTrigger className="flex items-center text-sm text-muted-foreground">
              <span>Version History</span>
              <ChevronDown className="h-4 w-4 ml-1" />
            </CollapsibleTrigger>
            <CollapsibleContent className="border-l-4 border-primary pl-4 mt-2">
              <div className="max-h-80 overflow-y-auto pr-4">
                <div className="space-y-4">
                  {score.versionHistory.map((version: VersionHistoryItem, index: number) => (
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
                      <div className="flex items-center justify-end mt-2">
                        <div className="text-right mr-4">
                          <div className="text-lg font-bold">
                            {version.accuracy}% / {version.distribution.reduce((sum: number, item: DistributionItem) => 
                              sum + item.value, 0)}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            Accuracy
                          </div>
                        </div>
                        <div className="w-[60px] h-[60px]">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={version.distribution}
                                dataKey="value"
                                nameKey="category"
                                cx="50%"
                                cy="50%"
                                innerRadius={0}
                                outerRadius={25}
                                fill="var(--true)"
                                strokeWidth={0}
                              >
                                {version.distribution.map((entry: DistributionItem, index: number) => (
                                  <Cell key={`cell-${index}`} fill={index === 0 ? "var(--true)" : "var(--false)"} />
                                ))}
                              </Pie>
                              <Pie
                                data={[
                                  { category: "Positive", value: 50 },
                                  { category: "Negative", value: 50 },
                                ]}
                                dataKey="value"
                                nameKey="category"
                                cx="50%"
                                cy="50%"
                                innerRadius={27}
                                outerRadius={30}
                                fill="var(--chart-2)"
                                strokeWidth={0}
                              >
                                {[0, 1].map((_, index) => (
                                  <Cell key={`cell-${index}`} fill={index === 0 ? "var(--true)" : "var(--false)"} />
                                ))}
                              </Pie>
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      );
    };

    const handleAddSection = async () => {
      if (!selectedScorecard) return
      
      const maxOrder = Math.max(0, ...selectedScorecard.sections.map(s => s.order))
      
      const newSection = {
        id: '',
        name: "New section",
        order: maxOrder + 1,
        scores: []
      }
      
      setSelectedScorecard({
        ...selectedScorecard,
        sections: [...selectedScorecard.sections, newSection]
      })
    }

    return (
      <Card className="rounded-none sm:rounded-lg h-full flex flex-col bg-card-light border-none">
        <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between py-4 px-4 sm:px-6 space-y-0">
          <div className="flex-grow">
            <EditableField
              value={selectedScorecard.name}
              onChange={(value) => setSelectedScorecard({ ...selectedScorecard, name: value })}
              className="text-xl font-semibold"
            />
          </div>
          <div className="flex ml-2">
            {!isNarrowViewport && (
              <Button variant="outline" size="icon" onClick={() => setIsFullWidth(!isFullWidth)}>
                {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
              </Button>
            )}
            <Button variant="outline" size="icon" onClick={() => {
              setSelectedScorecard(null);
              setIsFullWidth(false);
              setIsDetailViewFresh(true);
            }} className="ml-2">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex-grow overflow-auto px-4 sm:px-6 pb-4">
          <div className="space-y-4">
            <div className="flex justify-between">
              <EditableField 
                value={selectedScorecard.key} 
                onChange={(value) => setSelectedScorecard({ ...selectedScorecard, key: value })}
                className="font-mono"
              />
              <EditableField 
                value={selectedScorecard.id} 
                onChange={(value) => setSelectedScorecard({ ...selectedScorecard, id: value })}
                className="font-mono"
              />
            </div>
            
            <div className="mt-8">
              {selectedScorecard.sections.map((section, sectionIndex) => (
                <div key={section.id || sectionIndex} className="mb-6">
                  <div className="-mx-4 sm:-mx-6 mb-4">
                    <div className="bg-card px-4 sm:px-6 py-2">
                      <EditableField
                        value={section.name}
                        onChange={(value) => {
                          const updatedSections = [...selectedScorecard.sections]
                          updatedSections[sectionIndex] = { ...section, name: value }
                          setSelectedScorecard({ ...selectedScorecard, sections: updatedSections })
                        }}
                        className="text-md font-semibold"
                      />
                    </div>
                  </div>
                  <div>
                    {section.scores.map((score) => renderScoreItem(score, section.id))}
                  </div>
                  <div className="mt-4">
                    <Button variant="outline" onClick={() => handleAddScore(sectionIndex)}>
                      <Plus className="mr-2 h-4 w-4" /> Create Score
                    </Button>
                  </div>
                </div>
              ))}
              <div className="mt-6">
                <Button variant="outline" onClick={handleAddSection}>
                  <Plus className="mr-2 h-4 w-4" /> Create Section
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className={`flex flex-col flex-grow overflow-hidden pb-2`}>
        {selectedScorecard && (isNarrowViewport || isFullWidth) && (
          <div className="flex-shrink-0 h-full overflow-hidden">
            {renderSelectedItem()}
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
                                  <DropdownMenuItem>
                                    <AudioLines className="h-4 w-4 mr-2" /> Items
                                  </DropdownMenuItem>
                                  <DropdownMenuItem>
                                    <Siren className="h-4 w-4 mr-2" /> Alerts
                                  </DropdownMenuItem>
                                  <DropdownMenuItem>
                                    <FileBarChart className="h-4 w-4 mr-2" /> Reports
                                  </DropdownMenuItem>
                                  <DropdownMenuItem>
                                    <FlaskConical className="h-4 w-4 mr-2" /> Experiments
                                  </DropdownMenuItem>
                                  <DropdownMenuItem>
                                    <Zap className="h-4 w-4 mr-2" /> Optimizations
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
                            <DropdownMenuItem>
                              <AudioLines className="h-4 w-4 mr-2" /> Items
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Siren className="h-4 w-4 mr-2" /> Alerts
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <FileBarChart className="h-4 w-4 mr-2" /> Reports
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <FlaskConical className="h-4 w-4 mr-2" /> Experiments
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Zap className="h-4 w-4 mr-2" /> Optimizations
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
              <Button variant="outline" onClick={handleCreate}>
                <Plus className="mr-2 h-4 w-4" /> Create Scorecard
              </Button>
            </div>
          </div>

          {selectedScorecard && !isNarrowViewport && !isFullWidth && (
            <div className="flex-1 overflow-hidden">
              {selectedScorecard.sections.length > 0 ? 
                renderSelectedItem() : 
                <div>No sections configured yet</div>
              }
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

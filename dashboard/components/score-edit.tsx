"use client"
import React, { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { X, FlaskConical, Pencil, Check, GitCompareArrows } from 'lucide-react'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import KeywordClassifierComponent from './score-types/keyword-classifier'
import LangGraphScoreComponent from './score-types/lang-graph-score'
import ProgrammaticScoreComponent from './score-types/programmatic-score'
import ComputedScoreComponent from './score-types/computed-score'
import FuzzyMatchClassifierComponent from './score-types/fuzzy-match-classifier'
import SemanticClassifierComponent from './score-types/semantic-classifier'
import SimpleLLMScoreComponent from './score-types/simple-llm-score'
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { CardButton } from '@/components/CardButton'

interface ScoreEditProps {
  scorecardId: string
  scoreId: string
}

interface EditableFieldProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

interface ScoreMetadata {
  configuration: any
  distribution: any[]
  versionHistory: any[]
}

interface ScoreState {
  id: string
  name: string
  type: string
  order: number
  sectionId: string
  accuracy: number
  version: string
  aiProvider: string
  aiModel: string
  metadata: ScoreMetadata
  section?: Schema['ScorecardSection']['type']
  createdAt?: string
  updatedAt?: string
}

type ScorecardSectionRecord = Schema['ScorecardSection']['type']
type ScoreRecord = Schema['Score']['type']

const client = generateClient<Schema>()

const listSections = async (scorecardId: string) => {
  const response = await (client.models.ScorecardSection as any).list({
    filter: { scorecardId: { eq: scorecardId } }
  })
  return response.data as Schema['ScorecardSection']['type'][]
}

const listScores = async (sectionId: string) => {
  const response = await (client.models.Score as any).list({
    filter: { sectionId: { eq: sectionId } }
  })
  return response.data as Schema['Score']['type'][]
}

const getScore = async (id: string) => {
  const response = await (client.models.Score as any).get({ id })
  return response.data as Schema['Score']['type'] | null
}

const getSection = async (id: string) => {
  const response = await (client.models.ScorecardSection as any).get({ id })
  return response.data as Schema['ScorecardSection']['type'] | null
}

const createScore = async (scoreData: {
  name: string
  type: string
  order: number
  sectionId: string
  accuracy: number
  aiProvider: string
  aiModel: string
  configuration: any
  distribution: any[]
  versionHistory: any[]
}) => {
  const response = await (client.models.Score as any).create(scoreData)
  return response.data as Schema['Score']['type']
}

const updateScore = async (scoreData: {
  id: string
  name: string
  type: string
  order: number
  accuracy: number
  aiProvider: string
  aiModel: string
  configuration: any
  distribution: any[]
  versionHistory: any[]
}) => {
  const response = await (client.models.Score as any).update(scoreData)
  return response.data as Schema['Score']['type']
}

function EditableField({ value, onChange, className = "" }: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [tempValue, setTempValue] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isEditing])

  const handleEditToggle = () => {
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
            className={`py-1 px-2 ${className}`}
          />
          <CardButton
            icon={Check}
            onClick={handleSave}
          />
          <CardButton
            icon={X}
            onClick={handleCancel}
          />
        </>
      ) : (
        <>
          <span className={`${className}`}>{value}</span>
          <CardButton
            icon={Pencil}
            onClick={handleEditToggle}
          />
        </>
      )}
    </div>
  )
}

const defaultMetadata: ScoreMetadata = {
  configuration: {},
  distribution: [],
  versionHistory: []
}

const defaultState: ScoreState = {
  id: '',
  name: '',
  type: '',
  order: 0,
  sectionId: '',
  accuracy: 0,
  version: Date.now().toString(),
  aiProvider: 'OpenAI',
  aiModel: 'gpt-4',
  metadata: defaultMetadata
}

export default function ScoreEditComponent({ scorecardId, scoreId }: ScoreEditProps) {
  const router = useRouter()
  const [score, setScore] = useState<ScoreState | null>(null)
  const [section, setSection] = useState<Schema['ScorecardSection']['type'] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    fetchScore()
  }, [scorecardId, scoreId])

  const fetchScore = async () => {
    try {
      setIsLoading(true)
      if (scoreId === 'new') {
        const sections = await listSections(scorecardId)
        
        if (!sections.length) {
          throw new Error('No sections found in scorecard')
        }
        
        const defaultSection = sections[0]
        setSection(defaultSection)
        
        const scores = await listScores(defaultSection.id)
        const maxOrder = Math.max(0, ...scores.map(s => s.order))
        
        setScore({
          id: '',
          name: 'New Score',
          type: 'LangGraphScore',
          order: maxOrder + 1,
          sectionId: defaultSection.id,
          accuracy: 0,
          version: Date.now().toString(),
          aiProvider: 'OpenAI',
          aiModel: 'gpt-4',
          metadata: defaultMetadata,
          section: defaultSection,
          createdAt: undefined,
          updatedAt: undefined
        })
      } else {
        const scoreData = await getScore(scoreId)
        
        if (!scoreData) {
          throw new Error('Score not found')
        }
        
        setScore({
          id: scoreData.id,
          name: scoreData.name,
          type: scoreData.type,
          order: scoreData.order,
          sectionId: scoreData.sectionId,
          accuracy: scoreData.accuracy ?? 0,
          version: scoreData.version ?? Date.now().toString(),
          aiProvider: scoreData.aiProvider ?? 'OpenAI',
          aiModel: scoreData.aiModel ?? 'gpt-4',
          metadata: {
            configuration: (scoreData.configuration as ScoreMetadata | undefined)?.configuration ?? {},
            distribution: Array.isArray((scoreData.configuration as ScoreMetadata | undefined)?.distribution) ?
              (scoreData.configuration as ScoreMetadata).distribution : [],
            versionHistory: Array.isArray((scoreData.configuration as ScoreMetadata | undefined)?.versionHistory) ?
              (scoreData.configuration as ScoreMetadata).versionHistory : []
          } as ScoreMetadata,
          section: scoreData.section as unknown as Schema['ScorecardSection']['type'],
          createdAt: scoreData.createdAt,
          updatedAt: scoreData.updatedAt
        })
        
        const sectionData = await getSection(scoreData.sectionId)
        if (sectionData) {
          setSection(sectionData)
        }
      }
    } catch (error) {
      console.error('Error fetching score:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSave = async () => {
    if (!score || !section) return
    
    try {
      setIsSaving(true)
      
      if (!score.id) {
        const result = await createScore({
          name: score.name,
          type: score.type,
          order: score.order,
          sectionId: section.id,
          accuracy: score.accuracy,
          aiProvider: score.aiProvider,
          aiModel: score.aiModel,
          configuration: score.metadata.configuration,
          distribution: score.metadata.distribution,
          versionHistory: score.metadata.versionHistory
        })
        console.log('Created score:', result)
      } else {
        const result = await updateScore({
          id: score.id,
          name: score.name,
          type: score.type,
          order: score.order,
          accuracy: score.accuracy,
          aiProvider: score.aiProvider,
          aiModel: score.aiModel,
          configuration: score.metadata.configuration,
          distribution: score.metadata.distribution,
          versionHistory: score.metadata.versionHistory
        })
        console.log('Updated score:', result)
      }
      
      router.back()
    } catch (error) {
      console.error('Error saving score:', error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleEvaluate = () => {
    // Evaluate the updated score data
    console.log("Evaluating score:", score)
    // Implement evaluation logic here
  }

  const handleCancel = () => {
    router.back()
  }

  const handleNameChange = (newName: string) => {
    if (!score) return
    setScore({ ...score, name: newName })
  }

  const handleIdChange = (newId: string) => {
    if (!score) return
    setScore({ ...score, id: newId })
  }

  const handleTypeChange = (newType: string) => {
    if (!score) return
    setScore({ ...score, type: newType })
  }

  const renderScoreTypeComponent = () => {
    if (!score) return null
    
    switch (score.type) {
      case 'ProgrammaticScore':
        return <ProgrammaticScoreComponent score={score} onChange={setScore} />
      case 'ComputedScore':
        return <ComputedScoreComponent score={score} onChange={setScore} />
      case 'KeywordClassifier':
        return <KeywordClassifierComponent score={score} onChange={setScore} />
      case 'FuzzyMatchClassifier':
        return <FuzzyMatchClassifierComponent score={score} onChange={setScore} />
      case 'SemanticClassifier':
        return <SemanticClassifierComponent score={score} onChange={setScore} />
      case 'SimpleLLMScore':
        return <SimpleLLMScoreComponent score={score} onChange={setScore} />
      case 'LangGraphScore':
        return <LangGraphScoreComponent score={score} onChange={setScore} />
      default:
        return <p>Select a score type to configure.</p>
    }
  }

  if (!score) return <div>Loading...</div>

  return (
    <div className="h-full flex flex-col">
      <div className="flex justify-between py-4 px-4 sm:px-6">
        <div className="space-y-1">
          <EditableField
            value={score.name}
            onChange={handleNameChange}
            className="text-2xl font-semibold"
          />
          <p className="text-sm text-muted-foreground">
            {section?.scorecard?.name} - {section?.name}
          </p>
          <EditableField
            value={score.id || 'New Score'}
            onChange={handleIdChange}
            className="text-sm font-mono"
          />
        </div>
        <CardButton
          icon={X}
          onClick={handleCancel}
        />
      </div>
      <div className="flex-grow flex flex-col overflow-hidden px-4 sm:px-6 pb-4">
        <div className="space-y-4 mb-6">
          <div className="flex justify-between items-end">
            <div className="space-y-2">
              <Label htmlFor="score-type">Score Type</Label>
              <Select value={score.type} onValueChange={handleTypeChange}>
                <SelectTrigger id="score-type" className="w-[200px]">
                  <SelectValue placeholder="Select a score type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ProgrammaticScore">ProgrammaticScore</SelectItem>
                  <SelectItem value="ComputedScore">ComputedScore</SelectItem>
                  <SelectItem value="KeywordClassifier">KeywordClassifier</SelectItem>
                  <SelectItem value="FuzzyMatchClassifier">FuzzyMatchClassifier</SelectItem>
                  <SelectItem value="SemanticClassifier">SemanticClassifier</SelectItem>
                  <SelectItem value="LangGraphScore">LangGraphScore</SelectItem>
                  <SelectItem value="SimpleLLMScore">SimpleLLMScore</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button variant="outline">
              <GitCompareArrows className="h-4 w-4 mr-2" />
              Dependencies
            </Button>
          </div>
        </div>
        <div className="flex-grow overflow-auto">
          {renderScoreTypeComponent()}
        </div>
      </div>
      <div className="flex justify-end space-x-4 py-4 px-4 sm:px-6">
        <CardButton
          icon={X}
          onClick={handleCancel}
        />
        <Button 
          onClick={handleSave} 
          disabled={isSaving}
        >
          <FlaskConical className="h-4 w-4 mr-2" />
          {isSaving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  )
}

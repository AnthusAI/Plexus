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

interface ScoreEditProps {
  scorecardId: string
  scoreId: string
}

interface EditableFieldProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
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
  isFineTuned: boolean
  configuration: any
  distribution: any[]
  versionHistory: any[]
  section?: Schema['ScorecardSection']['type']
  createdAt?: string
  updatedAt?: string
}

const client = generateClient<Schema>()

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
          <span className={`${className}`}>{value}</span>
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
        // For new scores, we need to fetch the section first
        const sections = await client.models.ScorecardSection.list({
          filter: {
            scorecardId: {
              eq: scorecardId
            }
          }
        })
        
        if (!sections.data.length) {
          throw new Error('No sections found in scorecard')
        }
        
        const defaultSection = sections.data[0]
        setSection(defaultSection)
        
        // Get max order in section
        const existingScores = await client.models.Score.list({
          filter: {
            sectionId: {
              eq: defaultSection.id
            }
          }
        })
        const maxOrder = Math.max(
          0, 
          ...existingScores.data.map(s => s.order)
        )
        
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
          isFineTuned: false,
          configuration: {},
          distribution: [],
          versionHistory: []
        })
      } else {
        // Fetch existing score
        const result = await client.models.Score.get({
          id: scoreId
        })
        
        if (!result.data) {
          throw new Error('Score not found')
        }
        
        // Convert API response to ScoreState, handling nullable values
        const scoreData: ScoreState = {
          id: result.data.id,
          name: result.data.name,
          type: result.data.type,
          order: result.data.order,
          sectionId: result.data.sectionId,
          accuracy: result.data.accuracy ?? 0,
          version: result.data.version ?? Date.now().toString(),
          aiProvider: result.data.aiProvider ?? 'OpenAI',
          aiModel: result.data.aiModel ?? 'gpt-4',
          isFineTuned: result.data.isFineTuned ?? false,
          configuration: result.data.configuration ?? {},
          distribution: (result.data.distribution as any[] | null) ?? [],
          versionHistory: (result.data.versionHistory as any[] | null) ?? [],
          createdAt: result.data.createdAt,
          updatedAt: result.data.updatedAt
        }
        
        setScore(scoreData)
        
        // Fetch associated section
        const sectionResult = await client.models.ScorecardSection.get({
          id: result.data.sectionId
        })
        
        if (sectionResult.data) {
          setSection(sectionResult.data)
        }
      }
    } catch (error) {
      console.error('Error fetching score:', error)
      // Handle error appropriately
    } finally {
      setIsLoading(false)
    }
  }

  const handleSave = async () => {
    if (!score || !section) return
    
    try {
      setIsSaving(true)
      
      if (!score.id) {
        // Create new score
        const result = await client.models.Score.create({
          name: score.name,
          type: score.type,
          order: score.order,
          sectionId: section.id,
          accuracy: score.accuracy,
          aiProvider: score.aiProvider,
          aiModel: score.aiModel,
          isFineTuned: score.isFineTuned,
          configuration: score.configuration,
          distribution: score.distribution,
          versionHistory: score.versionHistory
        })
        console.log('Created score:', result)
      } else {
        // Update existing score
        const result = await client.models.Score.update({
          id: score.id,
          name: score.name,
          type: score.type,
          order: score.order,
          accuracy: score.accuracy,
          aiProvider: score.aiProvider,
          aiModel: score.aiModel,
          isFineTuned: score.isFineTuned,
          configuration: score.configuration,
          distribution: score.distribution,
          versionHistory: score.versionHistory
        })
        console.log('Updated score:', result)
      }
      
      router.back()
    } catch (error) {
      console.error('Error saving score:', error)
      // Handle error appropriately
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
        <Button variant="ghost" size="icon" onClick={handleCancel} className="self-start">
          <X className="h-4 w-4" />
        </Button>
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
        <Button variant="outline" onClick={handleCancel}>
          Cancel
        </Button>
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

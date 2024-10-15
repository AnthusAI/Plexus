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

interface ScoreEditProps {
  scorecardId: string
  scoreId: string
}

interface EditableFieldProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
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
  const [score, setScore] = useState<any>(null)

  useEffect(() => {
    // Fetch the score data here
    // For now, we'll use dummy data
    setScore({
      id: "16732",
      name: "Sample Score",
      scorecardName: "SelectQuote Term Life v1",
      type: "LangGraphScore", // Default type
      accuracy: 85,
      aiProvider: "OpenAI",
      aiModel: "gpt-4-mini",
      isFineTuned: false
    })
  }, [scorecardId, scoreId])

  const handleEvaluate = () => {
    // Evaluate the updated score data
    console.log("Evaluating score:", score)
    // Implement evaluation logic here
  }

  const handleCancel = () => {
    router.back()
  }

  const handleNameChange = (newName: string) => {
    setScore({ ...score, name: newName })
  }

  const handleIdChange = (newId: string) => {
    setScore({ ...score, id: newId })
  }

  const handleTypeChange = (newType: string) => {
    setScore({ ...score, type: newType })
  }

  const renderScoreTypeComponent = () => {
    switch (score.type) {
      case 'KeywordClassifier':
        return <KeywordClassifierComponent score={score} onChange={setScore} />
      case 'LangGraphScore':
        return <LangGraphScoreComponent score={score} onChange={setScore} />
      default:
        return <p>Select a score type to configure.</p>
    }
  }

  if (!score) return <div>Loading...</div>

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex justify-between py-4 px-4 sm:px-6">
        <div className="space-y-1">
          <EditableField
            value={score.name}
            onChange={handleNameChange}
            className="text-2xl font-semibold"
          />
          <p className="text-sm text-muted-foreground">{score.scorecardName}</p>
          <EditableField
            value={score.id}
            onChange={handleIdChange}
            className="text-sm font-mono"
          />
        </div>
        <Button variant="ghost" size="icon" onClick={handleCancel} className="self-start">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-grow overflow-auto px-4 sm:px-6 pb-4">
        <div className="space-y-4">
          <div className="flex justify-between items-end">
            <div className="space-y-2">
              <Label htmlFor="score-type">Score Type</Label>
              <Select value={score.type} onValueChange={handleTypeChange}>
                <SelectTrigger id="score-type" className="w-[200px]">
                  <SelectValue placeholder="Select a score type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ProgrammaticScore">ProgrammaticScore</SelectItem>
                  <SelectItem value="KeywordClassifier">KeywordClassifier</SelectItem>
                  <SelectItem value="FuzzyMatchClassifier">FuzzyMatchClassifier</SelectItem>
                  <SelectItem value="SemanticClassifier">SemanticClassifier</SelectItem>
                  <SelectItem value="BERTClassifier">BERTClassifier</SelectItem>
                  <SelectItem value="LangGraphScore">LangGraphScore</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button variant="outline">
              <GitCompareArrows className="h-4 w-4 mr-2" />
              Dependencies
            </Button>
          </div>
          {renderScoreTypeComponent()}
        </div>
      </div>
      <div className="flex justify-end space-x-4 py-4 px-4 sm:px-6">
        <Button variant="outline" onClick={handleCancel}>
          Cancel
        </Button>
        <Button onClick={handleEvaluate}>
          <FlaskConical className="h-4 w-4 mr-2" />
          Evaluate Changes
        </Button>
      </div>
    </div>
  )
}

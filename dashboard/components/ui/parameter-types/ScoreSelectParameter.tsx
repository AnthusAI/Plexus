"use client"

import React, { useEffect, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ParameterDefinition } from '@/types/parameters'
import { generateClient } from 'aws-amplify/data'
import type { Schema } from '@/amplify/data/resource'

const client = generateClient<Schema>()

interface ScoreSelectParameterProps {
  definition: ParameterDefinition
  value: string
  onChange: (value: string) => void
  scorecardId?: string
  error?: string
}

export function ScoreSelectParameter({ definition, value, onChange, scorecardId, error }: ScoreSelectParameterProps) {
  const [scores, setScores] = useState<Array<{ id: string; name: string }>>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!scorecardId) {
      setScores([])
      return
    }

    const loadScores = async () => {
      setIsLoading(true)
      try {
        const result = await client.graphql({
          query: `
            query GetScorecardScores($scorecardId: ID!) {
              getScorecard(id: $scorecardId) {
                scores {
                  items {
                    id
                    name
                    key
                  }
                }
              }
            }
          `,
          variables: { scorecardId }
        })
        
        const scoreData = (result as any).data?.getScorecard?.scores?.items || []
        setScores(scoreData.map((s: any) => ({ id: s.id, name: s.name })))
      } catch (error) {
        console.error('Error loading scores:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadScores()
  }, [scorecardId])

  const isDisabled = !scorecardId || isLoading

  return (
    <div className="space-y-2">
      <Label htmlFor={definition.name}>
        {definition.label}
        {definition.required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {definition.description && (
        <p className="text-xs text-muted-foreground">{definition.description}</p>
      )}
      <Select value={value || ''} onValueChange={onChange} disabled={isDisabled}>
        <SelectTrigger id={definition.name} className={error ? 'border-destructive' : ''}>
          <SelectValue 
            placeholder={
              !scorecardId 
                ? 'Select a scorecard first' 
                : isLoading 
                ? 'Loading scores...' 
                : definition.placeholder || 'Select a score'
            } 
          />
        </SelectTrigger>
        <SelectContent>
          {scores.map((score) => (
            <SelectItem key={score.id} value={score.id}>
              {score.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}




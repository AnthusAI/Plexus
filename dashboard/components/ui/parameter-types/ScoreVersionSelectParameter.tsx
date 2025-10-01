"use client"

import React, { useEffect, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ParameterDefinition } from '@/types/parameters'
import { generateClient } from 'aws-amplify/data'
import type { Schema } from '@/amplify/data/resource'

const client = generateClient<Schema>()

interface ScoreVersionSelectParameterProps {
  definition: ParameterDefinition
  value: string
  onChange: (value: string) => void
  scoreId?: string
  error?: string
}

export function ScoreVersionSelectParameter({ definition, value, onChange, scoreId, error }: ScoreVersionSelectParameterProps) {
  const [versions, setVersions] = useState<Array<{ id: string; createdAt: string; isFeatured: boolean }>>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!scoreId) {
      setVersions([])
      return
    }

    const loadVersions = async () => {
      setIsLoading(true)
      try {
        const result = await client.graphql({
          query: `
            query GetScoreVersionsByScoreId($scoreId: String!, $sortDirection: ModelSortDirection) {
              listScoreVersionByScoreIdAndCreatedAt(
                scoreId: $scoreId,
                sortDirection: $sortDirection
              ) {
                items {
                  id
                  scoreId
                  isFeatured
                  createdAt
                  updatedAt
                }
              }
            }
          `,
          variables: {
            scoreId: String(scoreId),
            sortDirection: 'DESC' // Newest first
          }
        })
        
        const versionData = (result as any).data?.listScoreVersionByScoreIdAndCreatedAt?.items || []
        // Sort by featured first, then keep chronological order from query
        const sorted = [...versionData].sort((a: any, b: any) => {
          if (a.isFeatured && !b.isFeatured) return -1
          if (!a.isFeatured && b.isFeatured) return 1
          return 0 // Keep DESC order from query
        })
        setVersions(sorted.map((v: any) => ({ 
          id: v.id, 
          createdAt: v.createdAt,
          isFeatured: v.isFeatured || false
        })))
      } catch (error) {
        console.error('Error loading score versions:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadVersions()
  }, [scoreId])

  const isDisabled = !scoreId || isLoading

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
              !scoreId 
                ? 'Select a score first' 
                : isLoading 
                ? 'Loading versions...' 
                : definition.placeholder || 'Select a version (optional)'
            } 
          />
        </SelectTrigger>
        <SelectContent>
          {versions.map((version) => (
            <SelectItem key={version.id} value={version.id}>
              {version.isFeatured && '⭐ '}
              {new Date(version.createdAt).toLocaleString()}
              <span className="text-muted-foreground ml-2 text-xs">({version.id.substring(0, 8)}...)</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}




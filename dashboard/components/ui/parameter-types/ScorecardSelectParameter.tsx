"use client"

import React, { useEffect, useState } from 'react'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ParameterDefinition } from '@/types/parameters'
import { generateClient } from 'aws-amplify/data'
import type { Schema } from '@/amplify/data/resource'
import { useAccount } from '@/app/contexts/AccountContext'

const client = generateClient<Schema>()

interface ScorecardSelectParameterProps {
  definition: ParameterDefinition
  value: string
  onChange: (value: string) => void
  error?: string
}

export function ScorecardSelectParameter({ definition, value, onChange, error }: ScorecardSelectParameterProps) {
  const { selectedAccount } = useAccount()
  const [scorecards, setScorecards] = useState<Array<{ id: string; name: string }>>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!selectedAccount?.id) return

    const loadScorecards = async () => {
      setIsLoading(true)
      try {
        const result = await client.graphql({
          query: `
            query ListScorecards($filter: ModelScorecardFilterInput) {
              listScorecards(filter: $filter) {
                items {
                  id
                  name
                  key
                  accountId
                }
                nextToken
              }
            }
          `,
          variables: {
            filter: { accountId: { eq: selectedAccount.id } }
          }
        })
        
        const scorecardData = (result as any).data?.listScorecards?.items || []
        setScorecards(scorecardData.map((sc: any) => ({ id: sc.id, name: sc.name })))
      } catch (error) {
        console.error('Error loading scorecards:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadScorecards()
  }, [selectedAccount?.id])

  return (
    <div className="space-y-2">
      <Label htmlFor={definition.name}>
        {definition.label}
        {definition.required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {definition.description && (
        <p className="text-xs text-muted-foreground">{definition.description}</p>
      )}
      <Select value={value || ''} onValueChange={onChange} disabled={isLoading}>
        <SelectTrigger id={definition.name} className={error ? 'border-destructive' : ''}>
          <SelectValue placeholder={isLoading ? 'Loading scorecards...' : definition.placeholder || 'Select a scorecard'} />
        </SelectTrigger>
        <SelectContent>
          {scorecards.map((scorecard) => (
            <SelectItem key={scorecard.id} value={scorecard.id}>
              {scorecard.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}




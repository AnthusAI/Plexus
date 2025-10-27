"use client"

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { ParameterDefinition, ParameterValue } from '@/types/parameters'
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"

type ParameterValues = ParameterValue
import { CheckCircle, XCircle } from 'lucide-react'

const client = generateClient<Schema>()

interface ParametersDisplayProps {
  parameters: ParameterDefinition[]
  values: ParameterValues
  compact?: boolean
  variant?: 'card' | 'table'
}

export function ParametersDisplay({
  parameters,
  values,
  compact = false,
  variant = 'card'
}: ParametersDisplayProps) {
  const [displayNames, setDisplayNames] = useState<Record<string, string>>({})

  // Fetch names for scorecard, score, and score version IDs
  useEffect(() => {
    const fetchNames = async () => {
      const names: Record<string, string> = {}
      
      for (const param of parameters) {
        const value = values[param.name]
        if (!value) continue

        try {
          if (param.type === 'scorecard_select') {
            const result = await client.graphql({
              query: `
                query GetScorecard($id: ID!) {
                  getScorecard(id: $id) {
                    id
                    name
                  }
                }
              `,
              variables: { id: value }
            })
            const scorecard = (result as any).data?.getScorecard
            if (scorecard?.name) {
              names[param.name] = scorecard.name
            }
          } else if (param.type === 'score_select') {
            const result = await client.graphql({
              query: `
                query GetScore($id: ID!) {
                  getScore(id: $id) {
                    id
                    name
                  }
                }
              `,
              variables: { id: value }
            })
            const score = (result as any).data?.getScore
            if (score?.name) {
              names[param.name] = score.name
            }
          } else if (param.type === 'score_version_select') {
            const result = await client.graphql({
              query: `
                query GetScoreVersion($id: ID!) {
                  getScoreVersion(id: $id) {
                    id
                    createdAt
                    isFeatured
                  }
                }
              `,
              variables: { id: value }
            })
            const version = (result as any).data?.getScoreVersion
            if (version) {
              const timestamp = new Date(version.createdAt).toLocaleString()
              const idPrefix = version.id.substring(0, 8)
              const star = version.isFeatured ? '⭐ ' : ''
              names[param.name] = `${star}${timestamp} (${idPrefix}...)`
            }
          }
        } catch (error) {
          console.error(`Error fetching name for ${param.type}:`, error)
        }
      }
      
      setDisplayNames(names)
    }

    fetchNames()
  }, [parameters, values])

  const formatValue = (param: ParameterDefinition, value: any): string => {
    if (value === undefined || value === null || value === '') {
      return '—'
    }

    switch (param.type) {
      case 'boolean':
        return value ? 'Yes' : 'No'
      case 'date':
        try {
          return new Date(value).toLocaleDateString()
        } catch {
          return String(value)
        }
      case 'select':
        // Find the option label if options are defined
        if (param.options) {
          const option = param.options.find(opt => opt.value === value)
          return option?.label || String(value)
        }
        return String(value)
      case 'scorecard_select':
      case 'score_select':
      case 'score_version_select':
        // Return the fetched name/display if available, otherwise show ID
        return displayNames[param.name] || String(value)
      default:
        return String(value)
    }
  }

  const renderBooleanIcon = (value: any) => {
    if (value === true) {
      return <CheckCircle className="h-4 w-4 text-green-600" />
    } else if (value === false) {
      return <XCircle className="h-4 w-4 text-red-600" />
    }
    return null
  }

  if (parameters.length === 0) {
    return null
  }

  if (compact) {
    return (
      <div className="flex flex-wrap gap-2">
        {parameters.map((param) => {
          const value = values[param.name]
          if (value === undefined || value === null || value === '') {
            return null
          }

          return (
            <Badge key={param.name} variant="secondary" className="flex items-center gap-1.5">
              <span className="text-xs font-medium">{param.label}:</span>
              {param.type === 'boolean' ? (
                renderBooleanIcon(value)
              ) : (
                <span className="text-xs">{formatValue(param, value)}</span>
              )}
            </Badge>
          )
        })}
      </div>
    )
  }

  if (variant === 'table') {
    return (
      <div className="border rounded-lg overflow-hidden">
        <table className="w-full">
          <tbody>
            {parameters.map((param) => {
              const value = values[param.name]
              return (
                <tr key={param.name} className="border-b last:border-b-0">
                  <td className="pr-4 py-3 text-sm font-medium text-muted-foreground w-1/3">
                    {param.label}
                    {param.required && <span className="text-destructive ml-1">*</span>}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      {param.type === 'boolean' && renderBooleanIcon(value)}
                      <span className={value === undefined || value === null || value === '' ? 'text-muted-foreground' : ''}>
                        {formatValue(param, value)}
                      </span>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <Card className="mb-4">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Parameters</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3">
          {parameters.map((param) => {
            const value = values[param.name]
            
            return (
              <div key={param.name} className="flex flex-col">
                <dt className="text-sm font-medium text-muted-foreground mb-1">
                  {param.label}
                  {param.required && <span className="text-destructive ml-1">*</span>}
                </dt>
                <dd className="text-sm flex items-center gap-2">
                  {param.type === 'boolean' && renderBooleanIcon(value)}
                  <span className={value === undefined || value === null || value === '' ? 'text-muted-foreground' : ''}>
                    {formatValue(param, value)}
                  </span>
                </dd>
              </div>
            )
          })}
        </dl>
      </CardContent>
    </Card>
  )
}


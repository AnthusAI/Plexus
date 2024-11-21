import React, { useEffect, useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { ModelListResult, AmplifyListResult } from '@/types/shared'
import { listFromModel } from "@/utils/amplify-helpers"

export const client = generateClient<Schema>()

export interface ScorecardContextProps {
  selectedScorecard: string | null;
  setSelectedScorecard: (value: string | null) => void;
  selectedScore: string | null;
  setSelectedScore: (value: string | null) => void;
  availableFields?: Array<{ value: string; label: string }>;
  timeRangeOptions?: Array<{ value: string; label: string }>;
  useMockData?: boolean;
}

async function listScorecards(): ModelListResult<Schema['Scorecard']['type']> {
  return listFromModel<Schema['Scorecard']['type']>(client.models.Scorecard)
}

async function listSections(scorecardId: string): ModelListResult<Schema['ScorecardSection']['type']> {
  return listFromModel<Schema['ScorecardSection']['type']>(
    client.models.ScorecardSection,
    { scorecardId: { eq: scorecardId } }
  )
}

async function listScores(sectionId: string): ModelListResult<Schema['Score']['type']> {
  return listFromModel<Schema['Score']['type']>(
    client.models.Score,
    { sectionId: { eq: sectionId } }
  )
}

const ScorecardContext: React.FC<ScorecardContextProps> = ({ 
  selectedScorecard, 
  setSelectedScorecard, 
  selectedScore, 
  setSelectedScore,
  availableFields: mockFields,
  timeRangeOptions: mockScores,
  useMockData = false
}) => {
  const [scorecards, setScorecards] = useState<Array<{ value: string; label: string }>>([])
  const [scores, setScores] = useState<Array<{ value: string; label: string }>>([])
  const [isLoading, setIsLoading] = useState(!useMockData)

  useEffect(() => {
    if (useMockData) return

    async function fetchScorecards() {
      try {
        const { data: scorecardModels } = await listScorecards()
        
        const formattedScorecards = scorecardModels.map(scorecard => ({
          value: scorecard.id,
          label: scorecard.name
        }))
        setScorecards(formattedScorecards)
      } catch (error) {
        console.error('Error fetching scorecards:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchScorecards()
  }, [useMockData])

  useEffect(() => {
    if (useMockData || !selectedScorecard) return

    async function fetchScores() {
      try {
        if (!selectedScorecard) return

        const { data: sections } = await listSections(selectedScorecard)
        
        const scorePromises = sections.map(async section => {
          const { data: scores } = await listScores(section.id)
          return scores
        })

        const scoreResults = await Promise.all(scorePromises)
        const uniqueScores = new Set<string>()
        
        scoreResults.flat().forEach(score => {
          if (score?.name) {
            uniqueScores.add(score.name)
          }
        })

        setScores(Array.from(uniqueScores).map(name => ({
          value: name,
          label: name
        })))
      } catch (error) {
        console.error('Error fetching scores:', error)
      }
    }

    fetchScores()
  }, [selectedScorecard, useMockData])

  if (isLoading) {
    return <div>Loading scorecards...</div>
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Select onValueChange={value => {
        setSelectedScorecard(value === "all" ? null : value)
      }}>
        <SelectTrigger className="w-[200px] h-10">
          <SelectValue placeholder="Scorecard" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Scorecards</SelectItem>
          {scorecards?.map(field => (
            <SelectItem key={field.value} value={field.value}>
              {field.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select 
        onValueChange={value => setSelectedScore(value === "all" ? null : value)}
        disabled={!selectedScorecard}
        value={selectedScore || "all"}
      >
        <SelectTrigger className="w-[200px] h-10">
          <SelectValue placeholder="Score" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Scores</SelectItem>
          {selectedScorecard && scores?.map(option => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export default ScorecardContext

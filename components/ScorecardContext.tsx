import React, { useEffect, useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"

const client = generateClient<Schema>()

export interface ScorecardContextProps {
  selectedScorecard: string | null;
  setSelectedScorecard: (value: string | null) => void;
  selectedScore: string | null;
  setSelectedScore: (value: string | null) => void;
  availableFields?: Array<{ value: string; label: string }>;
  timeRangeOptions?: Array<{ value: string; label: string }>;
  useMockData?: boolean;
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
        const result = await client.models.Scorecard.list()
        const formattedScorecards = result.data.map(scorecard => ({
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
        const sections = await client.models.ScorecardSection.list({
          filter: { scorecardId: { eq: selectedScorecard } }
        })
        
        const allScores = await Promise.all(
          sections.data.map(section => 
            client.models.Score.list({
              filter: { sectionId: { eq: section.id } }
            })
          )
        )

        const uniqueScores = new Set<string>()
        allScores.flat().forEach(scoreList => 
          scoreList.data.forEach(score => 
            uniqueScores.add(score.name)
          )
        )

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

  const availableFields = useMockData ? mockFields : scorecards
  const timeRangeOptions = useMockData ? mockScores : scores

  if (isLoading) {
    return <div>Loading scorecards...</div>
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Select onValueChange={setSelectedScorecard}>
        <SelectTrigger className="w-[200px] h-10">
          <SelectValue placeholder="Scorecard" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Scorecards</SelectItem>
          {availableFields?.map(field => (
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
          {selectedScorecard && timeRangeOptions?.map(option => (
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

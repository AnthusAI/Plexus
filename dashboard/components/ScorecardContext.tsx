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
  skeletonMode?: boolean;
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
  useMockData = false,
  skeletonMode = false
}) => {
  const [scorecards, setScorecards] = useState<Array<{ value: string; label: string }>>([])
  const [scores, setScores] = useState<Array<{ value: string; label: string }>>([])
  const [isLoading, setIsLoading] = useState(!useMockData)

  // Debug logging
  useEffect(() => {
    console.debug('ScorecardContext state:', { 
      selectedScorecard, 
      selectedScore, 
      scoresCount: scores.length,
      scores: scores.map(s => ({ id: s.value, name: s.label }))
    });
  }, [selectedScorecard, selectedScore, scores]);

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

  // Reset score selection when scorecard changes
  useEffect(() => {
    if (selectedScore) {
      setSelectedScore(null);
    }
  }, [selectedScorecard, setSelectedScore]);

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
        const allScores = scoreResults.flat();
        
        console.debug('Fetched scores for scorecard:', {
          scorecardId: selectedScorecard,
          scoresCount: allScores.length,
          scores: allScores.map(s => ({ id: s.id, name: s.name }))
        });
        
        // Use score IDs instead of names for values
        setScores(allScores.map(score => ({
          value: score.id,
          label: score.name
        })))
      } catch (error) {
        console.error('Error fetching scores:', error)
      }
    }

    fetchScores()
  }, [selectedScorecard, useMockData])

  const handleScoreChange = (value: string) => {
    console.debug('Score selection changed:', { 
      newValue: value, 
      previousValue: selectedScore 
    });
    setSelectedScore(value === "all" ? null : value);
  };

  return (
    <div className="flex flex-wrap gap-2">
      <Select 
        onValueChange={skeletonMode ? undefined : (value => {
          setSelectedScorecard(value === "all" ? null : value)
        })}
        value={skeletonMode ? undefined : (selectedScorecard || "all")}
        disabled={skeletonMode}
      >
        <SelectTrigger className={`w-[200px] h-9 bg-card border-none ${skeletonMode ? 'animate-pulse' : ''}`}>
          <SelectValue placeholder="Scorecard" />
        </SelectTrigger>
        {!skeletonMode && (
          <SelectContent className="bg-card border-none">
            <SelectItem value="all">All Scorecards</SelectItem>
            {scorecards?.sort((a, b) => a.label.localeCompare(b.label)).map(field => (
              <SelectItem key={field.value} value={field.value}>
                {field.label}
              </SelectItem>
            ))}
          </SelectContent>
        )}
      </Select>
      <Select 
        onValueChange={skeletonMode ? undefined : handleScoreChange}
        disabled={skeletonMode || !selectedScorecard}
        value={skeletonMode ? undefined : (selectedScore || "all")}
      >
        <SelectTrigger className={`w-[200px] h-9 bg-card border-none ${skeletonMode ? 'opacity-50 animate-pulse' : ''}`}>
          <SelectValue placeholder="Score" />
        </SelectTrigger>
        {!skeletonMode && (
          <SelectContent className="bg-card border-none">
            <SelectItem value="all">All Scores</SelectItem>
            {selectedScorecard && scores?.sort((a, b) => a.label.localeCompare(b.label)).map(option => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        )}
      </Select>
    </div>
  )
}

export default ScorecardContext

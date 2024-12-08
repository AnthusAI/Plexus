import React, { useState, useMemo, useEffect } from 'react'
import { Split, Filter, Download } from 'lucide-react'
import { EvaluationTaskScoreResult } from './EvaluationTaskScoreResult'
import { AccuracyBar } from '@/components/ui/accuracy-bar'
import { CardButton } from '@/components/CardButton'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import type { Schema } from "@/amplify/data/resource"

interface FilterState {
  showCorrect: boolean | null  // null means show all
  predictedValue: string | null
  actualValue: string | null
}

export interface EvaluationTaskScoreResultsProps {
  results: Schema['ScoreResult']['type'][]
  accuracy: number
  selectedPredictedValue?: string | null
  selectedActualValue?: string | null
  onResultSelect?: (result: Schema['ScoreResult']['type']) => void
  selectedScoreResult?: Schema['ScoreResult']['type'] | null
  navigationControls?: React.ReactNode
}

export function EvaluationTaskScoreResults({ 
  results, 
  accuracy,
  selectedPredictedValue,
  selectedActualValue,
  onResultSelect,
  selectedScoreResult,
  navigationControls
}: EvaluationTaskScoreResultsProps) {
  const [filters, setFilters] = useState<FilterState>({
    showCorrect: null,
    predictedValue: null,
    actualValue: null,
  })

  useEffect(() => {
    setFilters(prev => ({
      ...prev,
      predictedValue: selectedPredictedValue ?? null,
      actualValue: selectedActualValue ?? null
    }))
  }, [selectedPredictedValue, selectedActualValue])

  const uniqueValues = useMemo(() => {
    const predicted = new Set<string>()
    const actual = new Set<string>()
    
    results.forEach(result => {
      const parsedMetadata = typeof result.metadata === 'string' ? 
        JSON.parse(JSON.parse(result.metadata)) : 
        result.metadata

      const firstResultKey = parsedMetadata?.results ? 
        Object.keys(parsedMetadata.results)[0] : null
      const scoreResult = firstResultKey ? 
        parsedMetadata.results[firstResultKey] : null

      if (scoreResult?.value) predicted.add(scoreResult.value)
      if (scoreResult?.metadata?.human_label) actual.add(scoreResult.metadata.human_label)
    })
    
    return {
      predicted: Array.from(predicted).sort(),
      actual: Array.from(actual).sort()
    }
  }, [results])

  const filteredResults = useMemo(() => {
    return results.filter(result => {
      const parsedMetadata = typeof result.metadata === 'string' ? 
        JSON.parse(JSON.parse(result.metadata)) : 
        result.metadata

      const firstResultKey = parsedMetadata?.results ? 
        Object.keys(parsedMetadata.results)[0] : null
      const scoreResult = firstResultKey ? 
        parsedMetadata.results[firstResultKey] : null
      
      const isCorrect = scoreResult?.metadata?.correct ?? false
      
      if (filters.showCorrect !== null && isCorrect !== filters.showCorrect) {
        return false
      }
      
      if (filters.predictedValue && 
          scoreResult?.value !== filters.predictedValue) {
        return false
      }

      if (filters.actualValue && 
          scoreResult?.metadata?.human_label !== filters.actualValue) {
        return false
      }
      
      return true
    })
  }, [results, filters])

  const filteredAccuracy = useMemo(() => {
    if (filteredResults.length === 0) return null
    const correctCount = filteredResults.filter(r => {
      const parsedMetadata = typeof r.metadata === 'string' ? 
        JSON.parse(JSON.parse(r.metadata)) : 
        r.metadata

      const firstResultKey = parsedMetadata?.results ? 
        Object.keys(parsedMetadata.results)[0] : null
      const scoreResult = firstResultKey ? 
        parsedMetadata.results[firstResultKey] : null

      if (typeof scoreResult?.value === 'number') {
        return scoreResult.value === 1
      }
      return scoreResult?.value === 'Yes' || scoreResult?.value === 'Present'
    }).length
    return (correctCount / filteredResults.length) * 100
  }, [filteredResults])

  const handleAccuracySegmentClick = (isCorrect: boolean) => {
    setFilters(prev => ({
      ...prev,
      showCorrect: prev.showCorrect === isCorrect ? null : isCorrect,
      // Clear other filters when selecting correct/incorrect
      predictedValue: null,
      actualValue: null
    }))
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-none relative mb-1">
        <div className="flex items-start">
          <Split className="w-4 h-4 mr-1 text-foreground shrink-0" />
          <span className="text-sm text-foreground">
            {filteredResults.length} Predictions
          </span>
        </div>
        <div className="absolute bottom-1 right-0 flex items-center gap-2">
          {navigationControls}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <div>
                <CardButton
                  icon={Filter}
                  active={filters.showCorrect !== null || 
                         filters.predictedValue !== null || 
                         filters.actualValue !== null}
                />
              </div>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuCheckboxItem
                checked={filters.showCorrect === true}
                onCheckedChange={() => setFilters(f => ({
                  ...f,
                  showCorrect: f.showCorrect === true ? null : true
                }))}
              >
                Show Only Correct
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem
                checked={filters.showCorrect === false}
                onCheckedChange={() => setFilters(f => ({
                  ...f,
                  showCorrect: f.showCorrect === false ? null : false
                }))}
              >
                Show Only Incorrect
              </DropdownMenuCheckboxItem>
              
              <DropdownMenuSeparator />
              
              {uniqueValues.predicted.map(value => (
                <DropdownMenuCheckboxItem
                  key={`predicted-${value}`}
                  checked={filters.predictedValue === value}
                  onCheckedChange={() => setFilters(f => ({
                    ...f,
                    predictedValue: f.predictedValue === value ? null : value
                  }))}
                >
                  Predicted: {value}
                </DropdownMenuCheckboxItem>
              ))}

              <DropdownMenuSeparator />
              
              {uniqueValues.actual.map(value => (
                <DropdownMenuCheckboxItem
                  key={`actual-${value}`}
                  checked={filters.actualValue === value}
                  onCheckedChange={() => setFilters(f => ({
                    ...f,
                    actualValue: f.actualValue === value ? null : value
                  }))}
                >
                  Actual: {value}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <CardButton
            icon={Download}
            onClick={() => {}}
          />
        </div>
      </div>
      <div className="flex-none mb-4">
        <AccuracyBar 
          accuracy={filteredAccuracy} 
          onSegmentClick={handleAccuracySegmentClick}
        />
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="space-y-2">
          {filteredResults.map((result) => (
            <div 
              key={result.id}
              onClick={() => onResultSelect?.(result)}
              className="cursor-pointer"
            >
              <EvaluationTaskScoreResult
                id={result.id}
                value={result.value}
                confidence={result.confidence}
                metadata={result.metadata}
                correct={
                  typeof result.value === 'number' 
                    ? result.value === 1 
                    : result.value === 'Yes' || result.value === 'Present'
                }
                isFocused={selectedScoreResult?.id === result.id}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
} 
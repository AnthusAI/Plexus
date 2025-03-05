import React, { useState, useMemo, useEffect, useCallback } from 'react'
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
  results: {
    id: string
    value: string | number
    confidence: number | null
    explanation: string | null
    metadata: {
      human_label: string | null
      correct: boolean
    }
    itemId: string | null
  }[]
  accuracy: number | null
  selectedPredictedValue?: string | null
  selectedActualValue?: string | null
  onResultSelect?: (result: any) => void
  selectedScoreResult?: any | null
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
  console.log('EvaluationTaskScoreResults render:', {
    resultCount: results.length,
    firstResult: results[0],
    lastResult: results[results.length - 1],
    accuracy,
    selectedPredictedValue,
    selectedActualValue,
    hasSelectedResult: !!selectedScoreResult,
    selectedScoreResultId: selectedScoreResult?.id
  });

  const [filters, setFilters] = useState<FilterState>({
    showCorrect: null,
    predictedValue: null,
    actualValue: null,
  })

  useEffect(() => {
    setFilters(prev => {
      const newPredicted = selectedPredictedValue?.toLowerCase() ?? null;
      const newActual = selectedActualValue?.toLowerCase() ?? null;
      
      if (prev.predictedValue === newPredicted && prev.actualValue === newActual) {
        return prev;
      }
      
      return {
        ...prev,
        predictedValue: newPredicted,
        actualValue: newActual
      };
    });
  }, [selectedPredictedValue, selectedActualValue])

  const uniqueValues = useMemo(() => {
    const predicted = new Set<string>()
    const actual = new Set<string>()
    
    results.forEach(result => {
      if (result.value !== undefined && result.value !== null) {
        predicted.add(String(result.value).toLowerCase())
      }
      if (result.metadata.human_label) {
        actual.add(result.metadata.human_label.toLowerCase())
      }
    })
    
    return {
      predicted: Array.from(predicted).sort(),
      actual: Array.from(actual).sort()
    }
  }, [results])

  const filteredResults = useMemo(() => {
    console.log('Filtering score results:', {
      totalResults: results.length,
      filters: {
        showCorrect: filters.showCorrect,
        predictedValue: filters.predictedValue,
        actualValue: filters.actualValue
      }
    });

    const filtered = results.filter(result => {
      if (filters.showCorrect !== null && result.metadata.correct !== filters.showCorrect) {
        return false
      }
      
      if (filters.predictedValue && String(result.value).toLowerCase() !== filters.predictedValue) {
        return false
      }

      if (filters.actualValue && result.metadata.human_label?.toLowerCase() !== filters.actualValue) {
        return false
      }
      
      return true
    });

    console.log('Filtered results:', {
      inputCount: results.length,
      filteredCount: filtered.length,
      firstFiltered: filtered[0],
      lastFiltered: filtered[filtered.length - 1]
    });

    return filtered;
  }, [results, filters]);

  const filteredAccuracy = useMemo(() => {
    if (filteredResults.length === 0) return null
    const correctCount = filteredResults.filter(r => r.metadata.correct).length
    return (correctCount / filteredResults.length) * 100
  }, [filteredResults])

  const handleAccuracySegmentClick = useCallback((isCorrect: boolean) => {
    setFilters(prev => ({
      ...prev,
      showCorrect: prev.showCorrect === isCorrect ? null : isCorrect,
      predictedValue: null,
      actualValue: null
    }))
  }, [])

  const handleFilterChange = useCallback((type: 'predicted' | 'actual', value: string | null) => {
    setFilters(prev => ({
      ...prev,
      predictedValue: type === 'predicted' ? (prev.predictedValue === value ? null : value) : prev.predictedValue,
      actualValue: type === 'actual' ? (prev.actualValue === value ? null : value) : prev.actualValue
    }))
  }, [])

  const handleCorrectFilterChange = useCallback((value: boolean | null) => {
    setFilters(prev => ({
      ...prev,
      showCorrect: prev.showCorrect === value ? null : value
    }))
  }, [])

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
                  onClick={() => {}}
                />
              </div>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuCheckboxItem
                checked={filters.showCorrect === true}
                onCheckedChange={() => handleCorrectFilterChange(true)}
              >
                Show Only Correct
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem
                checked={filters.showCorrect === false}
                onCheckedChange={() => handleCorrectFilterChange(false)}
              >
                Show Only Incorrect
              </DropdownMenuCheckboxItem>
              
              <DropdownMenuSeparator />
              
              {uniqueValues.predicted.map(value => (
                <DropdownMenuCheckboxItem
                  key={`predicted-${value}`}
                  checked={filters.predictedValue === value}
                  onCheckedChange={() => handleFilterChange('predicted', value)}
                >
                  Predicted: {value}
                </DropdownMenuCheckboxItem>
              ))}

              <DropdownMenuSeparator />
              
              {uniqueValues.actual.map(value => (
                <DropdownMenuCheckboxItem
                  key={`actual-${value}`}
                  checked={filters.actualValue === value}
                  onCheckedChange={() => handleFilterChange('actual', value)}
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
          accuracy={filters.showCorrect !== null ? filteredAccuracy : accuracy} 
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
                {...{
                  ...result,
                  value: String(result.value)
                }}
                isFocused={selectedScoreResult?.id === result.id}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
} 
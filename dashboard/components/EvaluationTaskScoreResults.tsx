import React, { useState, useMemo, useEffect, useCallback } from 'react'
import { Split, Filter, Download, Loader2 } from 'lucide-react'
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
import { ScoreResultComponent, ScoreResultData } from '@/components/ui/score-result'

interface FilterState {
  showCorrect: boolean | null  // null means show all
  predictedValue: string | null
  actualValue: string | null
}

export interface EvaluationTaskScoreResultsProps {
  results: ScoreResultData[]
  accuracy: number | null
  selectedPredictedValue?: string | null
  selectedActualValue?: string | null
  onResultSelect?: (result: any) => void
  selectedScoreResult?: any | null
  navigationControls?: React.ReactNode
  isLoading?: boolean
}

export function EvaluationTaskScoreResults({ 
  results, 
  accuracy,
  selectedPredictedValue,
  selectedActualValue,
  onResultSelect,
  selectedScoreResult,
  navigationControls,
  isLoading = false
}: EvaluationTaskScoreResultsProps) {
  console.log('EvaluationTaskScoreResults render:', {
    resultCount: results.length,
    firstResult: results[0],
    lastResult: results[results.length - 1],
    accuracy,
    selectedPredictedValue,
    selectedActualValue,
    hasSelectedResult: !!selectedScoreResult,
    selectedScoreResultId: selectedScoreResult?.id,
    isLoading
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

  const isFiltered = filters.showCorrect !== null || 
                     filters.predictedValue !== null || 
                     filters.actualValue !== null

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center mb-2 flex-shrink-0">
        <div className="flex items-center">
          <Split className="w-4 h-4 mr-1 text-foreground shrink-0" />
          <span className="text-sm text-foreground">
            Score Results ({filteredResults.length})
            {isLoading && (
              <span className="ml-2 text-xs text-muted-foreground inline-flex items-center">
                <Loader2 className="h-3 w-3 mr-1 inline animate-spin" />
                Loading more...
              </span>
            )}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {navigationControls}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <CardButton
                icon={Filter}
                active={isFiltered}
                onClick={() => {}}
              />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
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
      <div className="flex-none z-10 mb-4">
        <AccuracyBar 
          accuracy={filters.showCorrect !== null ? filteredAccuracy : accuracy} 
          onSegmentClick={handleAccuracySegmentClick}
        />
      </div>
      <div className="flex-1 min-h-0 overflow-hidden">
        <div className="h-full overflow-y-auto">
          {results.length === 0 && isLoading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <span className="ml-2 text-muted-foreground">Loading score results...</span>
            </div>
          ) : (
            <>
              <div className="space-y-2 pb-4">
                {filteredResults.map((result) => (
                  <div key={result.id}>
                    <ScoreResultComponent
                      result={result}
                      variant="list"
                      isFocused={selectedScoreResult?.id === result.id}
                      onSelect={() => onResultSelect?.(result)}
                    />
                  </div>
                ))}
                {filteredResults.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    No score results match the current filters
                  </div>
                )}
              </div>
              
              {isLoading && (
                <div className="flex justify-center items-center py-4 border-t border-border">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground mr-2" />
                  <span className="text-sm text-muted-foreground">Loading more results...</span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
} 
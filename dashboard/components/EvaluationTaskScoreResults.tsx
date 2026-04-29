import React, { useState, useMemo, useEffect, useCallback } from 'react'
import { Split, Filter, Download } from 'lucide-react'
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
  selectedItemIds?: string[] | null
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
  selectedItemIds,
  onResultSelect,
  selectedScoreResult,
  navigationControls,
  isLoading = false
}: EvaluationTaskScoreResultsProps) {
  const toNormalized = (value: unknown): string | null => {
    if (value === null || value === undefined) return null
    const normalized = String(value).trim()
    return normalized.length > 0 ? normalized : null
  }

  const getResultFilterKeys = (result: ScoreResultData): string[] => {
    const keys = new Set<string>()
    const resultId = toNormalized(result.id)
    if (resultId) keys.add(resultId)
    const itemId = toNormalized(result.itemId)
    if (itemId) keys.add(itemId)

    const metadataItemId = toNormalized((result as any)?.metadata?.item_id)
    if (metadataItemId) keys.add(metadataItemId)

    const feedbackItemId = toNormalized((result as any)?.feedbackItem?.id)
    if (feedbackItemId) keys.add(feedbackItemId)
    const metadataFeedbackItemId = toNormalized((result as any)?.metadata?.feedback_item_id)
    if (metadataFeedbackItemId) keys.add(metadataFeedbackItemId)

    if (Array.isArray(result.itemIdentifiers)) {
      result.itemIdentifiers.forEach((identifier: any) => {
        const value = toNormalized(identifier?.value)
        if (value) keys.add(value)
      })
    }

    return Array.from(keys)
  }

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
    const normalizedSelectedItemIds = selectedItemIds
      ? new Set(selectedItemIds.map(toNormalized).filter((id): id is string => id !== null))
      : null

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

      if (normalizedSelectedItemIds) {
        const resultKeys = getResultFilterKeys(result)
        const hasMatch = resultKeys.some(key => normalizedSelectedItemIds.has(key))
        if (!hasMatch) return false
      }

      return true
    });

    return filtered;
  }, [results, filters, selectedItemIds]);

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
          <span className="text-sm text-foreground">Score Results</span>
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
          <div className="space-y-2 pb-4">
            {isLoading ? (
              Array.from({ length: 8 }).map((_, idx) => (
                <div key={`skeleton-${idx}`} className="animate-pulse rounded-lg bg-card-light px-2 py-3">
                  <div className="h-4 w-40 bg-muted rounded mb-2" />
                  <div className="h-3 w-24 bg-muted rounded" />
                </div>
              ))
            ) : (
              filteredResults.map((result) => (
                <div key={result.id}>
                  <ScoreResultComponent
                    result={result}
                    variant="list"
                    isFocused={selectedScoreResult?.id === result.id}
                    onSelect={() => onResultSelect?.(result)}
                  />
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

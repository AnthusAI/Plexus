import React, { useState, useMemo } from 'react'
import { Split, Filter, Download } from 'lucide-react'
import { ExperimentTaskScoreResult } from '@/components/ExperimentTaskScoreResult'
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

export interface ExperimentTaskScoreResultsProps {
  results: Schema['ScoreResult']['type'][]
  accuracy: number
}

export function ExperimentTaskScoreResults({ 
  results, 
  accuracy 
}: ExperimentTaskScoreResultsProps) {
  const [filters, setFilters] = useState<FilterState>({
    showCorrect: null,
    predictedValue: null,
    actualValue: null,
  })

  const uniqueValues = useMemo(() => {
    const predicted = new Set<string>()
    const actual = new Set<string>()
    
    results.forEach(result => {
      const metadata = JSON.parse(result.metadata)
      if (metadata.predicted_value) predicted.add(metadata.predicted_value)
      if (metadata.true_value) actual.add(metadata.true_value)
    })
    
    return {
      predicted: Array.from(predicted).sort(),
      actual: Array.from(actual).sort()
    }
  }, [results])

  const filteredResults = useMemo(() => {
    return results.filter(result => {
      const metadata = JSON.parse(result.metadata)
      const isCorrect = result.value === 1
      
      if (filters.showCorrect !== null && isCorrect !== filters.showCorrect) {
        return false
      }
      
      if (filters.predictedValue && 
          metadata.predicted_value !== filters.predictedValue) {
        return false
      }
      
      if (filters.actualValue && 
          metadata.true_value !== filters.actualValue) {
        return false
      }
      
      return true
    })
  }, [results, filters])

  return (
    <div className="flex flex-col h-full">
      <div className="relative">
        <div className="flex items-start">
          <Split className="w-4 h-4 mr-1 mt-0.5 text-foreground shrink-0" />
          <span className="text-sm text-foreground">
            {filteredResults.length} Predictions
          </span>
        </div>
        <div className="absolute bottom-0 right-0 flex items-center gap-1">
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
      <div className="flex flex-col flex-1 gap-4 mt-1">
        <AccuracyBar accuracy={accuracy} />
        <div className="flex-1 overflow-y-auto">
          <div className="space-y-2">
            {filteredResults.map((result) => (
              <ExperimentTaskScoreResult
                key={result.id}
                id={result.id}
                value={result.value}
                confidence={result.confidence}
                metadata={result.metadata}
                correct={result.value === 1}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
} 
import React from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export interface ScorecardContextProps {
  selectedScorecard: string | null;
  setSelectedScorecard: (value: string | null) => void;
  selectedScore: string | null;
  setSelectedScore: (value: string | null) => void;
  availableFields: Array<{ value: string; label: string }>;
  timeRangeOptions: Array<{ value: string; label: string }>;
}

const ScorecardContext: React.FC<ScorecardContextProps> = ({ 
  selectedScorecard, 
  setSelectedScorecard, 
  selectedScore, 
  setSelectedScore,
  availableFields,
  timeRangeOptions
}) => {
  return (
    <div className="flex flex-wrap gap-2">
      <Select onValueChange={setSelectedScorecard}>
        <SelectTrigger className="w-[200px] h-10">
          <SelectValue placeholder="Scorecard" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Scorecards</SelectItem>
          {availableFields.map(field => (
            <SelectItem key={field.value} value={field.value}>{field.label}</SelectItem>
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
          {selectedScorecard && timeRangeOptions.map(option => (
            <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export default ScorecardContext

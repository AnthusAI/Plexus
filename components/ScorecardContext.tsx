import React from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface ScorecardContextProps {
  selectedScorecard: string | null;
  setSelectedScorecard: (value: string | null) => void;
  selectedScore: string | null;
  setSelectedScore: (value: string | null) => void;
}

const ScorecardContext: React.FC<ScorecardContextProps> = ({ 
  selectedScorecard, 
  setSelectedScorecard, 
  selectedScore, 
  setSelectedScore
}) => {
  return (
    <div className="flex flex-wrap gap-2">
      <Select onValueChange={setSelectedScorecard}>
        <SelectTrigger className="w-[200px] h-10">
          <SelectValue placeholder="Scorecard" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Scorecards</SelectItem>
          <SelectItem value="SelectQuote Term Life v1">SelectQuote Term Life v1</SelectItem>
          <SelectItem value="CS3 Nexstar v1">CS3 Nexstar v1</SelectItem>
          <SelectItem value="CS3 Services v2">CS3 Services v2</SelectItem>
          <SelectItem value="CS3 Audigy">CS3 Audigy</SelectItem>
          <SelectItem value="AW IB Sales">AW IB Sales</SelectItem>
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
          {selectedScorecard && (
            <>
              <SelectItem value="Good Call">Good Call</SelectItem>
              <SelectItem value="Agent Branding">Agent Branding</SelectItem>
              <SelectItem value="Temperature Check">Temperature Check</SelectItem>
              <SelectItem value="Assumptive Close">Assumptive Close</SelectItem>
            </>
          )}
        </SelectContent>
      </Select>
    </div>
  )
}

export default ScorecardContext

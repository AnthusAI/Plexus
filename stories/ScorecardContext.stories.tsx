import React, { useState } from "react"
import { StoryFn, Meta } from "@storybook/react"
import ScorecardContext from "@/components/ScorecardContext"
import { FilterConfig } from "@/components/filter-control"

export default {
  title: "Dashboards/ScorecardContext",
  component: ScorecardContext,
} as Meta

interface TemplateProps {
  handleFilterChange: (newFilters: FilterConfig) => void;
  handleTimeRangeChange: (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => void;
  handleSampleChange: (method: string, count: number) => void;
}

const Template: StoryFn<TemplateProps> = (args) => {
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)

  const availableFields = [
    { value: 'scorecard', label: 'Scorecard' },
    { value: 'id', label: 'ID' },
    { value: 'status', label: 'Status' },
    { value: 'score', label: 'Score' },
  ]

  const timeRangeOptions = [
    { value: "recent", label: "Recent" },
    { value: "review", label: "With Feedback" },
    { value: "custom", label: "Custom" },
  ]

  return (
    <ScorecardContext 
      selectedScorecard={selectedScorecard}
      setSelectedScorecard={setSelectedScorecard}
      selectedScore={selectedScore}
      setSelectedScore={setSelectedScore}
      availableFields={availableFields}
      timeRangeOptions={timeRangeOptions}
      {...args}
    />
  )
}

export const Default = Template.bind({})
Default.args = {
  handleFilterChange: () => {},
  handleTimeRangeChange: () => {},
  handleSampleChange: () => {},
}

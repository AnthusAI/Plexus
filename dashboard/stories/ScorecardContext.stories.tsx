import React from "react"
import { StoryFn, Meta } from "@storybook/react"
import ScorecardContext, { ScorecardContextProps } from "@/components/ScorecardContext"

export default {
  title: "General/ScorecardContext",
  component: ScorecardContext,
} as Meta

const Template: StoryFn<ScorecardContextProps> = (args) => <ScorecardContext {...args} />

export const Default = Template.bind({})
Default.args = {
  selectedScorecard: null,
  setSelectedScorecard: () => {},
  selectedScore: null,
  setSelectedScore: () => {},
  useMockData: true,
  availableFields: [
    { value: 'scorecard-1', label: 'Example Scorecard' },
    { value: 'scorecard-2', label: 'Example Scorecard' },
    { value: 'scorecard-3', label: 'CS3 Services v2' },
    { value: 'scorecard-4', label: 'Example Scorecard' },
  ],
  timeRangeOptions: [
    { value: "good-call", label: "Good Call" },
    { value: "example-score", label: "Example Score" },
    { value: "temperature-check", label: "Temperature Check" },
    { value: "example-score-2", label: "Example Score" },
  ],
}

export const Loading = Template.bind({})
Loading.args = {
  selectedScorecard: null,
  setSelectedScorecard: () => {},
  selectedScore: null,
  setSelectedScore: () => {},
  useMockData: false,
}

export const SkeletonMode = Template.bind({})
SkeletonMode.args = {
  selectedScorecard: null,
  setSelectedScorecard: () => {},
  selectedScore: null,
  setSelectedScore: () => {},
  skeletonMode: true,
}

import React from "react"
import { StoryFn, Meta } from "@storybook/react"
import ScorecardContext, { ScorecardContextProps } from "@/components/ScorecardContext"

export default {
  title: "Context/ScorecardContext",
  component: ScorecardContext,
} as Meta

const Template: StoryFn<ScorecardContextProps> = (args) => <ScorecardContext {...args} />

export const Default = Template.bind({})
Default.args = {
  selectedScorecard: null,
  setSelectedScorecard: () => {},
  selectedScore: null,
  setSelectedScore: () => {},
  availableFields: [
    { value: 'scorecard', label: 'Scorecard' },
    { value: 'id', label: 'ID' },
    { value: 'status', label: 'Status' },
    { value: 'score', label: 'Score' },
  ],
  timeRangeOptions: [
    { value: "recent", label: "Recent" },
    { value: "review", label: "With Feedback" },
    { value: "custom", label: "Custom" },
  ],
}

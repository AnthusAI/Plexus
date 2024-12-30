import React from "react"
import { StoryFn, Meta } from "@storybook/react"
import ItemContext from "@/components/ItemContext"
import { FilterConfig } from "@/components/filter-control"

export default {
  title: "Context/ItemContext",
  component: ItemContext,
} as Meta

interface TemplateProps {
  handleFilterChange: (newFilters: FilterConfig) => void;
  handleSampleChange: (method: string, count: number) => void;
  handleTimeRangeChange: (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => void;
}

const Template: StoryFn<TemplateProps> = (args) => {
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
    <ItemContext 
      availableFields={availableFields}
      timeRangeOptions={timeRangeOptions}
      {...args}
    />
  )
}

export const Default = Template.bind({})
Default.args = {
  handleFilterChange: () => {},
  handleSampleChange: () => {},
  handleTimeRangeChange: () => {},
}

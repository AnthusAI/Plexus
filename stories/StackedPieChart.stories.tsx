import React from 'react'
import { StoryFn, Meta } from '@storybook/react'
import StackedPieChart from '../components/StackedPieChart'

export default {
  title: 'Components/StackedPieChart',
  component: StackedPieChart,
} as Meta<typeof StackedPieChart>

const Template: StoryFn<typeof StackedPieChart> = (args) => <StackedPieChart {...args} />

export const Default = Template.bind({})
Default.args = {
  accuracy: 75
}

export const LowAccuracy = Template.bind({})
LowAccuracy.args = {
  accuracy: 25
}

export const HighAccuracy = Template.bind({})
HighAccuracy.args = {
  accuracy: 95
}

export const ZeroAccuracy = Template.bind({})
ZeroAccuracy.args = {
  accuracy: 0
}

export const FullAccuracy = Template.bind({})
FullAccuracy.args = {
  accuracy: 100
}

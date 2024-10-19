import React from 'react'
import { Story, Meta } from '@storybook/react'
import BeforeAfterPieCharts from '../components/BeforeAfterPieCharts'

export default {
  title: 'Components/BeforeAfterPieCharts',
  component: BeforeAfterPieCharts,
} as Meta

const Template: Story = (args) => <BeforeAfterPieCharts {...args} />

export const Default = Template.bind({})
Default.args = {
  before: {
    innerRing: [{ value: 30 }]
  },
  after: {
    innerRing: [{ value: 70 }]
  }
}

export const NoChange = Template.bind({})
NoChange.args = {
  before: {
    innerRing: [{ value: 50 }]
  },
  after: {
    innerRing: [{ value: 50 }]
  }
}

export const FullChange = Template.bind({})
FullChange.args = {
  before: {
    innerRing: [{ value: 0 }]
  },
  after: {
    innerRing: [{ value: 100 }]
  }
}

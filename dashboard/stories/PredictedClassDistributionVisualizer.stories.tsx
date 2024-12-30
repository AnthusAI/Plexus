import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import PredictedClassDistributionVisualizer from '../components/PredictedClassDistributionVisualizer'

const meta = {
  title: 'Data/PredictedClassDistributionVisualizer',
  component: PredictedClassDistributionVisualizer,
  parameters: {
    layout: 'padded',
  },
} satisfies Meta<typeof PredictedClassDistributionVisualizer>

export default meta
type Story = StoryObj<typeof PredictedClassDistributionVisualizer>

const Template: Story = {
  render: (args) => (
    <div className="space-y-8">
      <div>
        <h3 className="text-sm font-medium mb-2">Full Width</h3>
        <PredictedClassDistributionVisualizer {...args} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <h3 className="text-sm font-medium mb-2">Half Width</h3>
          <PredictedClassDistributionVisualizer {...args} />
        </div>
        <div>
          <h3 className="text-sm font-medium mb-2">Half Width</h3>
          <PredictedClassDistributionVisualizer {...args} />
        </div>
      </div>
    </div>
  ),
}

export const Binary: Story = {
  ...Template,
  args: {
    data: [
      { label: "Yes", count: 753 },
      { label: "No", count: 247 },
    ],
  },
}

export const MultiClass: Story = {
  ...Template,
  args: {
    data: [
      { label: "Class A", count: 412 },
      { label: "Class B", count: 298 },
      { label: "Class C", count: 201 },
      { label: "Class D", count: 79 },
      { label: "Class E", count: 23 },
    ],
  },
}

export const ManySmallClasses: Story = {
  ...Template,
  args: {
    data: [
      { label: "3rd Party Clinic", count: 301 },
      { label: "Agent calling for a Patient", count: 252 },
      { label: "Follow-up Appointment", count: 198 },
      { label: "New Patient Registration", count: 149 },
      { label: "Insurance Verification", count: 75 },
      { label: "Patient Referral", count: 60 },
      { label: "Lab Results Inquiry", count: 51 },
      { label: "Medication Refill Request", count: 45 },
      { label: "Appointment Cancellation", count: 32 },
      { label: "Telehealth Consultation", count: 30 },
      { label: "Patient Feedback", count: 20 },
      { label: "Emergency Contact", count: 17 },
      { label: "Billing Inquiry", count: 10 },
      { label: "Health Record Request", count: 5 },
    ],
  },
}

export const SingleClass: Story = {
  ...Template,
  args: {
    data: [
      { label: "Single Class", count: 1000 },
    ],
  },
}

export const NoData: Story = {
  ...Template,
  args: {
    data: [],
  },
}

export const All: Story = {
  render: () => (
    <div className="space-y-8">
      <div>
        <h3 className="text-lg font-medium">Binary</h3>
        <PredictedClassDistributionVisualizer 
          data={Binary.args?.data} 
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">Multi-Class</h3>
        <PredictedClassDistributionVisualizer 
          data={MultiClass.args?.data} 
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">Many Small Classes</h3>
        <PredictedClassDistributionVisualizer 
          data={ManySmallClasses.args?.data} 
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">Single Class</h3>
        <PredictedClassDistributionVisualizer 
          data={SingleClass.args?.data} 
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">No Data</h3>
        <PredictedClassDistributionVisualizer 
          data={NoData.args?.data} 
        />
      </div>
    </div>
  ),
} 
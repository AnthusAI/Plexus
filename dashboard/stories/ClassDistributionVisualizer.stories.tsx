import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import ClassDistributionVisualizer from '../components/ClassDistributionVisualizer'

const meta = {
  title: 'General/Components/ClassDistributionVisualizer',
  component: ClassDistributionVisualizer,
  parameters: {
    layout: 'padded',
  },
} satisfies Meta<typeof ClassDistributionVisualizer>

export default meta
type Story = StoryObj<typeof ClassDistributionVisualizer>

const Template: Story = {
  render: (args) => (
    <div className="space-y-8">
      <div>
        <h3 className="text-sm font-medium mb-2">Full Width</h3>
        <ClassDistributionVisualizer {...args} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <h3 className="text-sm font-medium mb-2">Half Width</h3>
          <ClassDistributionVisualizer {...args} />
        </div>
        <div>
          <h3 className="text-sm font-medium mb-2">Half Width</h3>
          <ClassDistributionVisualizer {...args} />
        </div>
      </div>
    </div>
  ),
}

export const BinaryBalanced: Story = {
  ...Template,
  args: {
    data: [
      { label: "Yes", count: 510 },
      { label: "No", count: 490 },
    ],
    isBalanced: true,
  },
}

export const BinaryImbalanced: Story = {
  ...Template,
  args: {
    data: [
      { label: "Yes", count: 753 },
      { label: "No", count: 247 },
    ],
    isBalanced: false,
  },
}

export const MultiClassBalanced: Story = {
  ...Template,
  args: {
    data: [
      { label: "Class A", count: 200 },
      { label: "Class B", count: 200 },
      { label: "Class C", count: 200 },
      { label: "Class D", count: 200 },
      { label: "Class E", count: 200 },
    ],
    isBalanced: true,
  },
}

export const MultiClassImbalanced: Story = {
  ...Template,
  args: {
    data: [
      { label: "Class A", count: 412 },
      { label: "Class B", count: 298 },
      { label: "Class C", count: 201 },
      { label: "Class D", count: 79 },
      { label: "Class E", count: 23 },
    ],
    isBalanced: false,
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
    isBalanced: false,
  },
}

export const SingleClass: Story = {
  ...Template,
  args: {
    data: [
      { label: "Single Class", count: 1000 },
    ],
    isBalanced: null,
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
        <h3 className="text-lg font-medium">Binary Balanced</h3>
        <ClassDistributionVisualizer 
          data={BinaryBalanced.args!.data}
          isBalanced={BinaryBalanced.args!.isBalanced}
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">Binary Imbalanced</h3>
        <ClassDistributionVisualizer 
          data={BinaryImbalanced.args!.data}
          isBalanced={BinaryImbalanced.args!.isBalanced}
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">Multi-Class Balanced</h3>
        <ClassDistributionVisualizer 
          data={MultiClassBalanced.args!.data}
          isBalanced={MultiClassBalanced.args!.isBalanced}
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">Multi-Class Imbalanced</h3>
        <ClassDistributionVisualizer 
          data={MultiClassImbalanced.args!.data}
          isBalanced={MultiClassImbalanced.args!.isBalanced}
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">Many Small Classes</h3>
        <ClassDistributionVisualizer 
          data={ManySmallClasses.args?.data} 
          isBalanced={ManySmallClasses.args?.isBalanced} 
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">Single Class</h3>
        <ClassDistributionVisualizer 
          data={SingleClass.args?.data} 
          isBalanced={SingleClass.args?.isBalanced} 
        />
      </div>
      
      <div>
        <h3 className="text-lg font-medium">No Data</h3>
        <ClassDistributionVisualizer 
          data={NoData.args?.data} 
        />
      </div>
    </div>
  ),
} 
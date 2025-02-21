import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { SampleSizeInput } from '@/components/task-dispatch'

const meta: Meta<typeof SampleSizeInput> = {
  title: 'Task Dispatch/SampleSizeInput',
  component: SampleSizeInput,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof SampleSizeInput>

export const Default: Story = {
  args: {
    value: 100,
    onChange: (value: number) => {
      console.log('Value changed:', value)
    }
  }
}

export const WithLimits: Story = {
  args: {
    value: 500,
    min: 10,
    max: 1000,
    onChange: (value: number) => {
      console.log('Value changed:', value)
    }
  }
}

export const WithCustomClassName: Story = {
  args: {
    value: 250,
    className: "w-[200px]",
    onChange: (value: number) => {
      console.log('Value changed:', value)
    }
  }
} 
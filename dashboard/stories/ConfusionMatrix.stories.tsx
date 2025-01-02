import React from "react"
import type { Meta, StoryObj } from "@storybook/react"
import { expect, within, userEvent } from "@storybook/test"
import { ConfusionMatrix } from "../components/confusion-matrix"
import { Card } from "@/components/ui/card"

const meta: Meta<typeof ConfusionMatrix> = {
  title: "Visualization/ConfusionMatrix",
  component: ConfusionMatrix,
  parameters: {
    layout: "padded",
  },
  argTypes: {
    onSelectionChange: { 
      action: 'selection changed',
      description: 'Fired when any selection is made, with predicted and actual values'
    },
  },
  decorators: [
    (Story) => (
      <div className="w-full">
        <Card className="p-4">
          <Story />
        </Card>
      </div>
    ),
  ],
}

export default meta
type Story = StoryObj<typeof ConfusionMatrix>

export const Matrix2x2: Story = {
  args: {
    data: {
      matrix: [
        [50, 10],
        [5, 35],
      ],
      labels: ["No", "Yes"],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Check title and labels
    await expect(canvas.getByText('Confusion matrix')).toBeInTheDocument()
    await expect(canvas.getByText('Actual')).toBeInTheDocument()
    await expect(canvas.getByText('Predicted')).toBeInTheDocument()
    
    // Check matrix values
    await expect(canvas.getByText('50')).toBeInTheDocument()
    await expect(canvas.getByText('10')).toBeInTheDocument()
    await expect(canvas.getByText('5')).toBeInTheDocument()
    await expect(canvas.getByText('35')).toBeInTheDocument()
    
    // Check class labels
    const noLabels = canvas.getAllByText('No')
    const yesLabels = canvas.getAllByText('Yes')
    await expect(noLabels).toHaveLength(2) // Row and column
    await expect(yesLabels).toHaveLength(2) // Row and column
  }
}

export const InvalidData: Story = {
  args: {
    data: {
      matrix: [[1]],
      labels: ["No", "Yes"], // Mismatched dimensions
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Error')).toBeInTheDocument()
    await expect(canvas.getByText('Invalid confusion matrix data')).toBeInTheDocument()
  }
}

export const Interactions: Story = {
  args: {
    data: {
      matrix: [
        [50, 10],
        [5, 35],
      ],
      labels: ["No", "Yes"],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Test cell interactions
    const cell = canvas.getByText('50')
    await userEvent.hover(cell)
    
    // Wait for tooltip to appear and verify its content
    const tooltipContent = await canvas.findByRole('tooltip')
    await expect(tooltipContent).toBeInTheDocument()
    await expect(within(tooltipContent).getByText('Count: 50')).toBeInTheDocument()
    await expect(within(tooltipContent).getByText('Predicted: No')).toBeInTheDocument()
    await expect(within(tooltipContent).getByText('Actual: No')).toBeInTheDocument()
    
    // Test row label interaction
    const rowLabel = canvas.getAllByText('No')[0]
    await userEvent.hover(rowLabel)
    
    // Wait for row label tooltip
    const rowTooltip = await canvas.findByRole('tooltip')
    await expect(within(rowTooltip).getByText('View')).toBeInTheDocument()
  }
}

export const ColorScaling: Story = {
  args: {
    data: {
      matrix: [
        [100, 1],
        [1, 1],
      ],
      labels: ["A", "B"],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const maxValueCell = canvas.getByText('100')
    const minValueCell = canvas.getAllByText('1')[0]
    
    // Check that max value cell has darker background
    const maxBgColor = maxValueCell.closest('div')?.style.backgroundColor
    const minBgColor = minValueCell.closest('div')?.style.backgroundColor
    await expect(maxBgColor).not.toBe(minBgColor)
    
    // Check text color contrast
    await expect(maxValueCell.closest('div')).toHaveClass('text-white')
    await expect(minValueCell.closest('div')).toHaveClass('text-primary')
  }
}

export const Matrix2x2WithLongNames: Story = {
  args: {
    data: {
      matrix: [
        [50, 10],
        [5, 35],
      ],
      labels: [
        "Chocolate Fudge Brownie Supreme",
        "Strawberry Cheesecake Delight",
      ],
    },
  },
}

export const Matrix3x3: Story = {
  args: {
    data: {
      matrix: [
        [30, 5, 2],
        [3, 40, 3],
        [1, 2, 35],
      ],
      labels: ["No", "Yes", "NA"],
    },
  },
}

export const LargeMatrix: Story = {
  args: {
    data: {
      matrix: [
        [45, 2, 1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1],
        [1, 38, 2, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
        [2, 1, 40, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0],
        [0, 1, 0, 35, 2, 1, 0, 0, 0, 1, 0, 0, 0, 1],
        [1, 0, 1, 1, 42, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        [0, 1, 0, 1, 0, 38, 2, 1, 0, 0, 0, 1, 0, 0],
        [1, 0, 0, 0, 1, 1, 36, 2, 1, 0, 0, 0, 1, 0],
        [0, 0, 1, 0, 0, 1, 1, 39, 0, 1, 0, 0, 0, 1],
        [0, 1, 0, 0, 0, 0, 1, 0, 41, 2, 1, 0, 0, 0],
        [1, 0, 0, 1, 0, 0, 0, 1, 1, 37, 0, 1, 0, 0],
        [0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 43, 2, 1, 0],
        [0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 38, 0, 1],
        [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 40, 2],
        [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 37],
      ],
      labels: [
        "Vanilla Bean Supreme",
        "Chocolate Fudge Brownie",
        "Strawberry Cheesecake",
        "Mint Chocolate Chip",
        "Salted Caramel Swirl",
        "Cookie Dough Delight",
        "Butter Pecan Crunch",
        "Rocky Road Adventure",
        "Pistachio Almond Dream",
        "Coffee Toffee Crunch",
        "Raspberry Ripple Royale",
        "Peanut Butter Paradise",
        "Coconut Cream Cloud",
        "Maple Walnut Wonder",
      ],
    },
  },
}

export const LargeMatrixSingleChar: Story = {
  args: {
    data: {
      matrix: [
        [45, 2, 1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 1],
        [1, 38, 2, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
        [2, 1, 40, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0],
        [0, 1, 0, 35, 2, 1, 0, 0, 0, 1, 0, 0, 0, 1],
        [1, 0, 1, 1, 42, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        [0, 1, 0, 1, 0, 38, 2, 1, 0, 0, 0, 1, 0, 0],
        [1, 0, 0, 0, 1, 1, 36, 2, 1, 0, 0, 0, 1, 0],
        [0, 0, 1, 0, 0, 1, 1, 39, 0, 1, 0, 0, 0, 1],
        [0, 1, 0, 0, 0, 0, 1, 0, 41, 2, 1, 0, 0, 0],
        [1, 0, 0, 1, 0, 0, 0, 1, 1, 37, 0, 1, 0, 0],
        [0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 43, 2, 1, 0],
        [0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 38, 0, 1],
        [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 40, 2],
        [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 37],
      ],
      labels: ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N"],
    },
  },
} 
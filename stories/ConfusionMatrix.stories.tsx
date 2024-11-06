import type { Meta, StoryObj } from "@storybook/react"
import { ConfusionMatrix } from "@/components/confusion-matrix"

const meta: Meta<typeof ConfusionMatrix> = {
  title: "Components/ConfusionMatrix",
  component: ConfusionMatrix,
  parameters: {
    layout: "padded",
  },
  decorators: [
    (Story) => (
      <div className="w-full">
        <Story />
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

export const Matrix4x4: Story = {
  args: {
    data: {
      matrix: [
        [45, 2, 3, 1],
        [3, 40, 2, 1],
        [2, 1, 35, 3],
        [1, 2, 1, 38],
      ],
      labels: ["Class 1", "Class 2", "Class 3", "Class 4"],
    },
  },
} 
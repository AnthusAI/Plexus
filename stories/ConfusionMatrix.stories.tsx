import React from "react"
import type { Meta, StoryObj } from "@storybook/react"
import { ConfusionMatrix } from "../components/confusion-matrix"
import { Card } from "@/components/ui/card"

const meta: Meta<typeof ConfusionMatrix> = {
  title: "Visualization/ConfusionMatrix",
  component: ConfusionMatrix,
  parameters: {
    layout: "padded",
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
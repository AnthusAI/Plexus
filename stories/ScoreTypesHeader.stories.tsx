import React from 'react'
import { Meta } from '@storybook/react'
import ScoreTypesHeader from '../components/ScoreTypesHeader'

export default {
  title: 'Components/ScoreTypesHeader',
  component: ScoreTypesHeader,
  decorators: [(Story) => (
    <div className="bg-background p-4">
      <Story />
    </div>
  )]
} as Meta

export const AllBadges = () => (
  <ScoreTypesHeader
    scoreType="binary"
    dataBalance="balanced"
    scoreGoal="precision"
  />
)

export const BinaryUnbalancedRecall = () => (
  <ScoreTypesHeader
    scoreType="binary"
    dataBalance="unbalanced"
    scoreGoal="recall"
  />
)

export const MulticlassBalancedBalanced = () => (
  <ScoreTypesHeader
    scoreType="multiclass"
    dataBalance="balanced"
    scoreGoal="balanced"
  />
)

export const PartialBadges = () => (
  <ScoreTypesHeader
    scoreType="binary"
    scoreGoal="precision"
  />
) 
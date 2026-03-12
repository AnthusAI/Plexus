import React from 'react'
import { Meta, StoryFn } from '@storybook/react'
import ScoreTypeBadge from '../components/ScoreTypeBadge'
import { 
  SquareSplitVertical, 
  Layers, 
  Scale, 
  EqualNot, 
  Target, 
  ShieldAlert 
} from 'lucide-react'

export default {
  title: 'General/Components/ScoreTypeBadge',
  component: ScoreTypeBadge,
  decorators: [(Story) => (
    <div className="bg-background p-4">
      <Story />
    </div>
  )]
} as Meta

// Score Types
export const ScoreTypes = () => (
  <div className="space-y-4">
    <ScoreTypeBadge
      icon={SquareSplitVertical}
      label="Binary"
      subLabel="2 classes"
      color="blue"
    />
    <ScoreTypeBadge
      icon={Layers}
      label="Multi-class"
      subLabel="3+ classes"
      color="purple"
    />
  </div>
)

// Data Balance
export const DataBalance = () => (
  <div className="space-y-4">
    <ScoreTypeBadge
      icon={Scale}
      label="Balanced"
      subLabel="Equal distribution"
      color="green"
    />
    <ScoreTypeBadge
      icon={EqualNot}
      label="Unbalanced"
      subLabel="Skewed distribution"
      color="yellow"
    />
  </div>
)

// Score Goals
export const ScoreGoals = () => (
  <div className="space-y-4">
    <ScoreTypeBadge
      icon={Target}
      label="Detect All Positives"
      subLabel="High recall"
      color="indigo"
    />
    <ScoreTypeBadge
      icon={ShieldAlert}
      label="Avoid False Positives"
      subLabel="High precision"
      color="red"
    />
    <ScoreTypeBadge
      icon={Scale}
      label="Balanced Approach"
      subLabel="High F1-score"
      color="orange"
    />
  </div>
) 
import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { FeatureCard } from '../components/landing/FeatureCard'
import { Shield, Headphones, Filter, Target } from 'lucide-react'

const meta: Meta<typeof FeatureCard> = {
  title: 'Landing/FeatureCard',
  component: FeatureCard,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof FeatureCard>

export const Default: Story = {
  args: {
    title: 'Call Center Quality Assurance',
    description: 'Automatically analyze customer service interactions to assess agent performance, detect emotional nuances, and ensure consistent service quality.',
    icon: Headphones,
  },
}

export const WithLink: Story = {
  args: {
    title: 'Call Center Quality Assurance',
    description: 'Automatically analyze customer service interactions to assess agent performance, detect emotional nuances, and ensure consistent service quality.',
    icon: Headphones,
    href: '/call-center-qa',
  },
}

export const ComplianceExample: Story = {
  args: {
    title: 'Regulatory Compliance at Scale',
    description: 'Process millions of communications and transactions to detect compliance violations across your entire organization.',
    icon: Shield,
  },
}

export const ContentCurationExample: Story = {
  args: {
    title: 'Brand-Aligned Content Curation',
    description: 'Intelligently select and rank content items that align with your brand\'s voice, values, and messaging across various platforms.',
    icon: Filter,
  },
}

export const SafetyExample: Story = {
  args: {
    title: 'Critical Safety Applications',
    description: 'Deploy high-stakes classification systems like automated threat detection in images for humanitarian demining operations.',
    icon: Target,
  },
}

// Example of a grid layout with multiple cards
export const GridLayout: Story = {
  decorators: [
    (Story) => (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 p-8 max-w-7xl">
        <FeatureCard
          title="Call Center Quality Assurance"
          description="Automatically analyze customer service interactions to assess agent performance, detect emotional nuances, and ensure consistent service quality."
          icon={Headphones}
        />
        <FeatureCard
          title="Brand-Aligned Content Curation"
          description="Intelligently select and rank content items that align with your brand's voice, values, and messaging across various platforms."
          icon={Filter}
        />
        <FeatureCard
          title="Regulatory Compliance at Scale"
          description="Process millions of communications and transactions to detect compliance violations across your entire organization."
          icon={Shield}
        />
        <FeatureCard
          title="Critical Safety Applications"
          description="Deploy high-stakes classification systems like automated threat detection in images for humanitarian demining operations."
          icon={Target}
        />
      </div>
    ),
  ],
} 
import React from 'react'
import { 
  Headphones, 
  Filter, 
  Shield,
  Target
} from 'lucide-react'
import { FeatureCard } from './FeatureCard'
import { StandardSection } from '@/components/landing/StandardSection'

const applications = [
  {
    title: "Call Center Quality Assurance",
    description: "Automatically analyze customer service interactions to assess agent performance, detect emotional nuances, and ensure consistent service quality.",
    icon: Headphones,
    href: "/call-center-qa"
  },
  {
    title: "Brand-Aligned Content Curation",
    description: "Intelligently select and rank content items that align with your brand's voice, values, and messaging across various platforms.",
    icon: Filter
  },
  {
    title: "Regulatory Compliance at Scale",
    description: "Process millions of communications and transactions to detect compliance violations across your entire organization.",
    icon: Shield
  },
  {
    title: "Critical Safety Applications",
    description: "Deploy high-stakes classification systems like automated threat detection in images for humanitarian demining operations.",
    icon: Target
  }
]

export const UseCases = () => {
  return (
    <StandardSection
      headline="Real-World Applications"
      headlinePosition="top"
      fullWidth
    >
      <div className="max-w-4xl mx-auto text-center mb-12">
        <p className="text-2xl text-muted-foreground mb-12">
          From automated business workflows to mission-critical operations, 
          our platform orchestrates intelligent decisions and actions at scale.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
        {applications.map((app, index) => (
          <FeatureCard
            key={index}
            title={app.title}
            description={app.description}
            icon={app.icon}
            href={app.href}
          />
        ))}
      </div>
    </StandardSection>
  )
} 
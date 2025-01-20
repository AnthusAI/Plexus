import React from 'react'
import { 
  Headphones, 
  Filter, 
  Mail, 
  ShieldCheck 
} from 'lucide-react'

const applications = [
  {
    title: "Call Center Quality Assurance",
    description: "Automatically analyze customer service interactions to assess agent performance, detect emotional nuances, and ensure consistent service quality.",
    icon: Headphones
  },
  {
    title: "Brand-Aligned Content Curation",
    description: "Intelligently select and rank content items that align with your brand's voice, values, and messaging across various platforms.",
    icon: Filter
  },
  {
    title: "Regulatory Compliance Monitoring",
    description: "Automatically detect and flag emails that may trigger regulatory issues, enabling proactive risk management and compliance.",
    icon: Mail
  },
  {
    title: "Automated Compliance Actions",
    description: "Trigger predefined workflows when sensitive communications are detected, ensuring immediate and appropriate response.",
    icon: ShieldCheck
  }
]

export const Applications = () => {
  return (
    <section className="py-20 bg-background">
      <div className="container mx-auto px-4">
        <div className="max-w-4xl mx-auto text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold mb-6 text-foreground">
            AI Agents at Scale
          </h2>
          <div className="space-y-6">
            <p className="text-xl text-muted-foreground">
              When data volumes become too large or complex for manual processing, 
              AI agents can transform how organizations extract value from their information.
            </p>
            <p className="text-xl text-muted-foreground">
              Plexus helps teams build AI workflows that can automatically analyze, 
              classify, and act on massive datasets across different domains and industries.
            </p>
            <p className="text-xl text-muted-foreground">
              Whether it's compliance, quality assurance, or content management, 
              intelligent automation can solve problems that were previously impossible to scale.
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {applications.map((app, index) => (
            <div key={index} 
                 className="bg-card p-6 rounded-lg shadow-md 
                           transition-all duration-300 hover:shadow-xl">
              <app.icon className="float-right ml-4 w-12 h-12 text-accent" />
              <h3 className="text-xl font-semibold mb-2 text-foreground">
                {app.title}
              </h3>
              <p className="text-muted-foreground">
                {app.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
} 
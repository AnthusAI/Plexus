import React from 'react'
import { 
  Headphones, 
  Filter, 
  Shield,
  Target
} from 'lucide-react'
import Link from 'next/link'

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
    <section className="py-20 bg-background">
      <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className="py-4">
          <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
            <div className="max-w-4xl mx-auto text-center mb-12">
              <h2 className="text-4xl md:text-5xl font-bold mb-8 text-foreground">
                Real-World Applications
              </h2>
              <p className="text-2xl text-muted-foreground mb-12">
                From automated business workflows to mission-critical operations, 
                our platform orchestrates intelligent decisions and actions at scale.
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
              {applications.map((app, index) => (
                <div key={index} 
                     className="bg-card p-6 rounded-lg shadow-md 
                               transition-all duration-300 hover:shadow-xl">
                  <app.icon className="float-right ml-4 w-12 h-12 text-accent" />
                  {app.href ? (
                    <Link href={app.href}>
                      <h3 className="text-xl font-semibold mb-2 text-foreground 
                                   hover:text-accent">
                        {app.title}
                      </h3>
                    </Link>
                  ) : (
                    <h3 className="text-xl font-semibold mb-2 text-foreground">
                      {app.title}
                    </h3>
                  )}
                  <p className="text-muted-foreground">
                    {app.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
} 
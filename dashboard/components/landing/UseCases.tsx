import React from 'react'
import { 
  Headphones, 
  Filter, 
  Shield,
  Target,
  Download,
  Brain,
  Workflow
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
    <>
      <section className="py-20 bg-background">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-4xl md:text-5xl font-bold mb-8 text-foreground 
                         bg-gradient-to-r from-accent to-accent-foreground 
                         bg-clip-text text-transparent">
              Intelligence at Scale
            </h2>
            <p className="text-2xl font-semibold mb-12 text-foreground">
              Transform how your organization handles information
            </p>
            <div className="grid md:grid-cols-3 gap-12 text-left">
              <div className="flex flex-col items-center text-center p-6 
                            rounded-lg transition-all duration-300 
                            hover:bg-accent/5">
                <Download className="w-16 h-16 mb-6 text-accent" />
                <h3 className="text-2xl font-bold mb-4 text-foreground">
                  Ingest
                </h3>
                <p className="text-lg text-muted-foreground">
                  Connect to your data sources and process millions of items 
                  automatically
                </p>
              </div>
              <div className="flex flex-col items-center text-center p-6 
                            rounded-lg transition-all duration-300 
                            hover:bg-accent/5">
                <Brain className="w-16 h-16 mb-6 text-accent" />
                <h3 className="text-2xl font-bold mb-4 text-foreground">
                  Analyze
                </h3>
                <p className="text-lg text-muted-foreground">
                  Build intelligent workflows that learn from your data and 
                  make predictions
                </p>
              </div>
              <div className="flex flex-col items-center text-center p-6 
                            rounded-lg transition-all duration-300 
                            hover:bg-accent/5">
                <Workflow className="w-16 h-16 mb-6 text-accent" />
                <h3 className="text-2xl font-bold mb-4 text-foreground">
                  Act
                </h3>
                <p className="text-lg text-muted-foreground">
                  Orchestrate automated responses across your enterprise systems
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-6 text-foreground">
              Real-World Applications
            </h2>
            <p className="text-xl text-muted-foreground">
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
      </section>
    </>
  )
} 
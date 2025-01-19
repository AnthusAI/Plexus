import React from 'react'
import { 
  PhoneCall, 
  Search, 
  Shield, 
  AudioLines 
} from 'lucide-react'

const applications = [
  {
    title: "Call Transcript Analysis",
    description: "Automatically process millions of telephone call transcripts to identify critical customer requests, like opt-out instructions or compliance issues.",
    icon: PhoneCall
  },
  {
    title: "Satellite & Drone Imagery",
    description: "Deploy AI models to detect and classify high-stakes objects like land mines in complex terrain, enhancing safety and reconnaissance capabilities.",
    icon: Shield
  },
  {
    title: "Large-Scale Content Ranking",
    description: "Build intelligent search and recommendation systems by ranking millions of content items using sophisticated multi-model classification.",
    icon: Search
  },
  {
    title: "Audio Quality Monitoring",
    description: "Analyze audio recordings to detect nuanced performance indicators, such as monotone speech patterns in customer service interactions.",
    icon: AudioLines
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
              Whether it's compliance, safety, search, or quality monitoring, 
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
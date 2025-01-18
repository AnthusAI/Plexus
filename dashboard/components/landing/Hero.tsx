import { Button } from "@/components/ui/button"
import { ArrowRight } from 'lucide-react'

export const Hero = () => {
  return (
    <section className="container mx-auto px-4 py-20 md:py-32">
      <div className="flex flex-col items-center text-center">
        <h1 className="text-5xl md:text-7xl font-bold tracking-tighter mb-6 max-w-4xl leading-tight">
          Orchestrate{' '}
          <span className="text-transparent bg-gradient-to-r from-fuchsia-500 to-fuchsia-600 bg-clip-text">
            AI agents
          </span>{' '}
          with{' '}
          <span className="text-transparent bg-gradient-to-r from-blue-500 to-blue-600 bg-clip-text">
            no code
          </span>
        </h1>
        <p className="text-xl md:text-2xl text-muted-foreground mb-8 max-w-3xl">
          Plexus is a battle-tested task-dispatching platform for building agent-based AI workflows that analyze streams of content and take action.
        </p>
        <div className="flex flex-col sm:flex-row gap-4">
          <Button size="lg" className="w-full sm:w-auto">
            Get Started
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          <Button size="lg" variant="outline" className="w-full sm:w-auto">
            Learn More
          </Button>
        </div>
      </div>
      <div className="mt-16 relative">
        <div className="absolute inset-0 bg-gradient-to-r from-fuchsia-500 to-blue-500 rounded-lg blur-2xl opacity-30"></div>
        <img
          src="/placeholder.svg?height=400&width=800"
          alt="Plexis AI Workflow"
          className="w-full rounded-lg shadow-2xl relative"
        />
      </div>
    </section>
  )
}


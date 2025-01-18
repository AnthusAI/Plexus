"use client"

import { Button } from "@/components/ui/button"
import { ArrowRight } from 'lucide-react'
import { useRouter } from 'next/navigation'

export const Hero = () => {
  const router = useRouter()

  return (
    <section className="container mx-auto px-4 py-20 md:py-32">
      <div className="flex flex-col items-center text-center">
        <h1 className="text-5xl md:text-7xl font-bold tracking-tighter mb-6 max-w-4xl leading-tight">
          Orchestrate{' '}
          <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text">
            AI agents
          </span>{' '}
          with{' '}
          <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">
            no code
          </span>
        </h1>
        <p className="text-xl md:text-2xl text-muted-foreground mb-8 max-w-3xl">
          Plexus is a battle-tested task-dispatching platform for building agent-based AI workflows that analyze streams of content and take action.
        </p>
        <div className="flex flex-col sm:flex-row gap-4">
          <Button size="lg" className="w-full sm:w-auto bg-primary text-white hover:bg-primary/90 text-lg font-semibold">
            Learn More
          </Button>
          <Button 
            size="lg" 
            className="w-full sm:w-auto bg-secondary text-white hover:bg-secondary/90 text-lg font-semibold"
            onClick={(e) => {
              e.preventDefault()
              router.push('/dashboard')
            }}
          >
            Log In
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </div>
      <div className="mt-16 relative">
        <div className="absolute inset-0 bg-gradient-to-r from-secondary to-primary rounded-lg blur-2xl opacity-30"></div>
        <img
          src="/placeholder.svg?height=400&width=800"
          alt="Plexus AI Workflow"
          className="w-full rounded-lg shadow-2xl relative"
        />
      </div>
    </section>
  )
}


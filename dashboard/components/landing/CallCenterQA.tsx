import React from 'react'
import { Button } from '@/components/ui/button'
import { ArrowRight } from 'lucide-react'

export const CallCenterQA = () => {
  return (
    <div className="container mx-auto px-4 max-w-7xl">
      <div className="py-16">
        <div className="max-w-3xl mx-auto text-center mb-16">
          <h1 className="text-4xl md:text-5xl font-bold mb-8 text-foreground 
                       bg-gradient-to-r from-accent to-accent-foreground 
                       bg-clip-text text-transparent">
            AI-Powered Call Center QA Platform
          </h1>
          <p className="text-2xl text-muted-foreground mb-12">
            Build, evaluate, and continuously improve AI scorecards for analyzing 
            call content at scale
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="bg-primary text-white">
              Explore Scorecards
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button size="lg" variant="outline">
              View Documentation
            </Button>
          </div>
        </div>
      </div>

      <section className="py-20">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-8 text-foreground">
            Start Building Your Scorecards
          </h2>
          <p className="text-xl text-muted-foreground mb-12">
            Deploy sophisticated AI analysis pipelines without getting locked into 
            a single model or approach
          </p>
          <Button size="lg" className="bg-primary text-white">
            Get Started
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </section>
    </div>
  )
} 
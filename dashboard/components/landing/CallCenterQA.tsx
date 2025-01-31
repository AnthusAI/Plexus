import React from 'react'
import { Button } from '@/components/ui/button'
import { ArrowRight } from 'lucide-react'
import { StandardSection } from './StandardSection'

export const CallCenterQA = () => {
  return (
    <>
      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-24 md:py-32 px-4 md:px-8">
              <div className="max-w-3xl mx-auto text-center">
                <h1 className="text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-8 text-foreground 
                           bg-gradient-to-r from-accent to-accent-foreground 
                           bg-clip-text text-transparent">
                  AI-Powered Call Center QA Platform
                </h1>
                <p className="text-xl text-muted-foreground mb-12">
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
          </div>
        </div>
      </section>

      <StandardSection
        headline="Start Building Your Scorecards"
        headlinePosition="top"
        fullWidth
      >
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-xl text-muted-foreground mb-12">
            Deploy sophisticated AI analysis pipelines without getting locked into 
            a single model or approach
          </p>
          <Button size="lg" className="bg-primary text-white">
            Get Started
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </StandardSection>
    </>
  )
} 
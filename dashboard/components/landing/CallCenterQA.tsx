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
                <h1 className="text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-8 leading-tight">
                  <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text whitespace-nowrap">Monitor calls</span> with <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">AI agents</span> with <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">no code</span>
                </h1>
                <p className="text-xl text-muted-foreground mb-6">
                  Replace expensive manual call quality assessments with AI-driven automation.
                  Save the cost of full-time QA staff while improving evaluation coverage and consistency.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12 text-left">
                  <div>
                    <h3 className="text-xl font-semibold mb-2">Eliminate Manual QA</h3>
                    <p className="text-muted-foreground">
                      Automate evaluations with AI to save the expense of full-time QA staff while increasing coverage.
                    </p>
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold mb-2">Accelerate Agent Growth</h3>
                    <p className="text-muted-foreground">
                      Help new hires reach full productivity faster with AI-powered training insights and feedback.
                    </p>
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold mb-2">Boost Team Performance</h3>
                    <p className="text-muted-foreground">
                      Provide real-time AI feedback to help your team excel and reduce turnover rates.
                    </p>
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <Button size="lg" className="bg-primary text-white">
                    Book a Demo
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
        headline="Enterprise-Ready Integration"
        headlinePosition="top"
        fullWidth
      >
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-xl text-muted-foreground mb-6">
            Seamlessly integrate with your existing call center infrastructure including RingCentral, Five9, Twilio, Microsoft Teams, and more.
          </p>
          <p className="text-xl text-muted-foreground mb-12">
            Qualified organizations receive a complimentary analysis of 100 interactions to demonstrate immediate value.
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
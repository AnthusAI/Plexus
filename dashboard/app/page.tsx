import React from 'react'
import { Hero } from '@/components/landing/Hero'
import { Features } from '@/components/landing/Features'
import { LabelingStrategies } from '@/components/landing/LabelingStrategies'
import { UseCases } from '@/components/landing/UseCases'
import { Overview } from '@/components/landing/Overview'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Layout } from '@/components/landing/Layout'
import { Download, Brain, Workflow as WorkflowIcon } from 'lucide-react'
import MultiModelWorkflow from '@/components/workflow/layouts/multi-model-workflow'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'

export default function LandingPage() {
  return (
    <Layout>
      <Hero />

      <section className="pt-20 pb-12 md:pb-20 bg-background">
        <div className="container mx-auto px-4">
          <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center gap-12">
            <div className="w-full md:w-2/5 relative p-4">
              <div className="relative z-10">
                <ItemListWorkflow />
              </div>
            </div>
            <div className="w-full md:w-3/5 text-center md:text-left">
              <h2 className="text-4xl md:text-5xl font-bold mb-10 text-foreground">
                Intelligence at Scale
              </h2>
              <p className="text-xl text-muted-foreground">
                Plexus runs a scorecard on each item in your data, with multiple scores per scorecard. 
                Are your agents saying the right things? Are your inbound leads qualified? Classify, predict, 
                extract, and act on your data.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="pt-0 pb-12 md:pb-20 bg-background">
        <div className="container mx-auto px-4">
          <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center gap-12">
            <div className="w-full md:w-3/5 text-center md:text-left">
              <h2 className="text-4xl md:text-5xl font-bold mb-10 text-foreground">
                Use Any Model
              </h2>
              <p className="text-xl text-muted-foreground">
                AI changes every week! Don't lock yourself into one solution. 
                Plexus is a workbench for applying any newfangled AI model to 
                solve your problems. Or simpler and cheaper ML models. Or 
                logical rules -- anything your solution requires.
              </p>
            </div>
            <div className="w-full md:w-2/5 relative p-4">
              <div className="relative z-10">
                <MultiModelWorkflow />
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="container mx-auto px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold mb-8 text-foreground">
            Organizational Intelligence
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
              <WorkflowIcon className="w-16 h-16 mb-6 text-accent" />
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

      <UseCases />
      <LabelingStrategies />
      <Features />
      <CTASection />
      <Footer />
    </Layout>
  )
} 
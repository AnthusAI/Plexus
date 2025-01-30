import React from 'react'
import { Hero } from '@/components/landing/Hero'
import { Features } from '@/components/landing/Features'
import { LabelingStrategies } from '@/components/landing/LabelingStrategies'
import { UseCases } from '@/components/landing/UseCases'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Layout } from '@/components/landing/Layout'
import { Download, Brain, Workflow as WorkflowIcon } from 'lucide-react'
import MultiModelWorkflow from '@/components/workflow/layouts/multi-model-workflow'
import MultiTypeWorkflow from '@/components/workflow/layouts/multi-type-workflow'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'
import MetricsGauges from '@/components/MetricsGauges'

export default function LandingPage() {
  return (
    <Layout>
      <Hero />

      <section className="pt-12 pb-8 md:pb-12 bg-background">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-6 md:py-8 px-4 md:px-8">
              <div className="flex flex-col md:flex-row items-center justify-between">
                <div className="w-full md:w-[45%] relative">
                  <div className="relative z-10">
                    <ItemListWorkflow />
                  </div>
                </div>
                <div className="w-full md:w-1/2 text-center md:text-left">
                  <h2 className="text-4xl md:text-5xl font-bold mb-6 text-foreground">
                    Intelligence at Scale
                  </h2>
                  <p className="text-xl text-muted-foreground text-justify">
                    Run a scorecard on each item of your data, with multiple scores per scorecard. 
                    Are your agents saying the right things? Are your inbound leads qualified? Classify, predict, 
                    extract, and act on your data.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-8 md:py-12 px-4 md:px-8">
              <div className="flex flex-col xl:flex-row gap-8">
                <div className="flex-1 min-w-0">
                  <h2 className="text-4xl md:text-5xl font-bold mb-6 md:mb-12 text-foreground text-center md:text-center xl:text-left">
                    Use Any Model
                  </h2>
                  <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                    <div className="w-full md:w-1/2 xl:w-full flex flex-col items-center md:items-start text-center md:text-left md:justify-center">
                      <p className="text-xl text-muted-foreground text-justify w-full">
                        AI changes every week! Don't lock yourself into one solution. 
                        Plexus is a workbench for applying any newfangled AI model to 
                        solve your problems. Or simpler and cheaper ML models. Or 
                        logical rules -- anything your solution requires.
                      </p>
                    </div>
                    <div className="w-full md:w-1/2 xl:hidden flex justify-center md:justify-end items-center">
                      <div className="w-full max-w-[400px]">
                        <MultiModelWorkflow />
                      </div>
                    </div>
                  </div>
                </div>
                <div className="hidden xl:flex flex-1 min-w-0 justify-center md:justify-end items-center">
                  <div className="w-full max-w-[400px]">
                    <MultiModelWorkflow />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="pt-20 pb-12 md:pb-20 bg-background">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-8 md:py-12 px-4 md:px-8">
              <div className="flex flex-col md:flex-row items-center justify-between">
                <div className="w-full md:w-[45%] relative">
                  <div className="relative z-10">
                    <MetricsGauges
                      variant="detail"
                      gauges={[
                        {
                          value: 92,
                          label: 'Accuracy',
                          backgroundColor: 'var(--gauge-background)',
                        },
                        {
                          value: 91,
                          label: 'Precision',
                          segments: [
                            { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                            { start: 60, end: 85, color: 'var(--gauge-converging)' },
                            { start: 85, end: 100, color: 'var(--gauge-great)' }
                          ],
                          backgroundColor: 'var(--gauge-background)',
                        },
                        {
                          value: 89,
                          label: 'Sensitivity',
                          segments: [
                            { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                            { start: 60, end: 85, color: 'var(--gauge-converging)' },
                            { start: 85, end: 100, color: 'var(--gauge-great)' }
                          ],
                          backgroundColor: 'var(--gauge-background)',
                          priority: true
                        },
                        {
                          value: 95,
                          label: 'Specificity',
                          segments: [
                            { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                            { start: 60, end: 85, color: 'var(--gauge-converging)' },
                            { start: 85, end: 100, color: 'var(--gauge-great)' }
                          ],
                          backgroundColor: 'var(--gauge-background)',
                        },
                      ]}
                    />
                  </div>
                </div>
                <div className="w-full md:w-1/2 text-center md:text-left">
                  <h2 className="text-4xl md:text-5xl font-bold mb-10 text-foreground">
                    Don't Just Guess — Guess and Test
                  </h2>
                  <p className="text-xl text-muted-foreground text-justify">
                    You can't just write prompts and put them into production and hope they work, you need a way to evaluate them quantitatively to see if they meet your needs.  You can't optimize a metric you're not measuring.
                  </p>
                  <p className="text-xl text-muted-foreground text-justify mt-4">
                    Different needs require different metrics: Is this a regulatory compliance question where we need high sensitivity? Do we need to use balanced accuracy because the data is unbalanced? Plexus gives you the gauges you need.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-8 md:py-12 px-4 md:px-8">
              <div className="flex flex-col xl:flex-row gap-8">
                <div className="flex-1 min-w-0">
                  <h2 className="text-4xl md:text-5xl font-bold mb-6 md:mb-12 text-foreground text-center md:text-center xl:text-left">
                    Any Result Type
                  </h2>
                  <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                    <div className="w-full md:w-1/2 xl:w-full flex flex-col items-center md:items-start text-center md:text-left md:justify-center">
                      <p className="text-xl text-muted-foreground text-justify w-full">
                        Different problems need different types of answers. Sometimes you need a simple yes/no, 
                        sometimes a 5-star rating, sometimes a percentage score, and sometimes just a thumbs up. 
                        Plexus gives you the flexibility to express your results in the format that makes sense 
                        for your use case.
                      </p>
                    </div>
                    <div className="w-full md:w-1/2 xl:hidden flex justify-center md:justify-end items-center">
                      <div className="w-full max-w-[400px]">
                        <MultiTypeWorkflow />
                      </div>
                    </div>
                  </div>
                </div>
                <div className="hidden xl:flex flex-1 min-w-0 justify-center md:justify-end items-center">
                  <div className="w-full max-w-[400px]">
                    <MultiTypeWorkflow />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <Features />

      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
              <div className="max-w-4xl mx-auto text-center">
                <h2 className="text-4xl md:text-5xl font-bold mb-8 text-foreground">
                  Organizational Intelligence
                </h2>
                <p className="text-2xl text-muted-foreground mb-12">
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
          </div>
        </div>
      </section>

      <UseCases />
      <CTASection />
      <Footer />
    </Layout>
  )
} 
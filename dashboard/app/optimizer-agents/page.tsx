import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { Button } from '@/components/ui/button'
import { ArrowRight } from 'lucide-react'
import { StandardSection } from '@/components/landing/StandardSection'
import { FrameSection } from '@/components/landing/FrameSection'
import BeforeAfterGauges from '@/components/BeforeAfterGauges'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'

export default function OptimizerAgentsPage() {
  return (
    <Layout>
      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
              <div className="flex flex-col xl:flex-row gap-8">
                <div className="flex-1 min-w-0 xl:w-[calc(50%-2rem)]">
                  <h1 className="text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-6 md:mb-12 leading-tight text-center md:text-center xl:text-left">
                    <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">Move the Needle</span> with <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text whitespace-nowrap">AI Agents</span> with <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">No Code</span>
                  </h1>
                  <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                    <div className="w-full md:w-1/2 xl:w-full flex flex-col items-center md:items-start text-center md:text-left md:justify-center">
                      <p className="text-xl text-muted-foreground mb-8 w-full">
                        Transform LLM-based classifiers from proof-of-concept to production-ready. Our optimizer agents automate the process of aligning prompts with your business needs, using a disciplined, scientific approach to prompt engineering.
                      </p>
                      <div className="flex flex-col sm:flex-row gap-4">
                        <Button size="lg" className="w-full sm:w-auto bg-primary text-white hover:bg-primary/90 text-lg font-semibold">
                          Learn More
                          <ArrowRight className="ml-2 h-5 w-5" />
                        </Button>
                      </div>
                    </div>
                    <div className="w-full md:w-1/2 xl:hidden flex justify-center md:justify-end items-center">
                      <div className="w-full max-w-[400px]">
                        <BeforeAfterGauges
                          title="Classification Accuracy"
                          before={72}
                          after={94}
                          segments={[
                            { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                            { start: 60, end: 85, color: 'var(--gauge-converging)' },
                            { start: 85, end: 100, color: 'var(--gauge-great)' }
                          ]}
                          variant="detail"
                          backgroundColor="var(--gauge-background)"
                        />
                      </div>
                    </div>
                  </div>
                </div>
                <div className="hidden xl:flex flex-1 min-w-0 xl:w-[calc(50%-2rem)] justify-center md:justify-end items-center">
                  <div className="w-full max-w-[400px]">
                    <BeforeAfterGauges
                      title="Classification Accuracy"
                      before={72}
                      after={94}
                      segments={[
                        { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                        { start: 60, end: 85, color: 'var(--gauge-converging)' },
                        { start: 85, end: 100, color: 'var(--gauge-great)' }
                      ]}
                      variant="detail"
                      backgroundColor="var(--gauge-background)"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <StandardSection
        headline="Automated Prompt Optimization"
        headlinePosition="top"
        leftContent={
          <p className="text-lg text-muted-foreground">
            While it's easy to create LLM-based classifiers with a few prompts, optimizing them for real-world performance is challenging. Optimizer agents bridge this gap by implementing a systematic, ML-inspired approach to prompt refinement, using Plexus's evaluation framework to measure and validate each improvement.
          </p>
        }
        rightContent={
          <p className="text-lg text-muted-foreground">
            Just like ML training uses gradient optimization, our agents use evaluation metrics to guide their decisions. They make targeted prompt adjustments, measure the impact, and iteratively improve performance—all while maintaining cost awareness and reproducibility.
          </p>
        }
      />

      <FrameSection
        headline="Battle-Tested Optimization Strategy"
        headlinePosition="top"
        layout="twoColumn"
        leftContent={
          <p className="text-lg text-muted-foreground">
            Built on our experience automating call center QA, our optimizer agents know when to make surgical adjustments versus complete rewrites. They explore the solution space methodically, balancing exploration with exploitation to find optimal prompts efficiently.
          </p>
        }
        rightContent={
          <p className="text-lg text-muted-foreground">
            The key is integration: Optimizer agents leverage Plexus's evaluation framework to make data-driven decisions. They validate each change against your labeled data, ensuring improvements are real and measurable, not just theoretical.
          </p>
        }
      />

      <StandardSection
        headline="Minimal Human Input Required"
        headlinePosition="top"
        leftContent={
          <p className="text-lg text-muted-foreground">
            Your team's expertise stays focused on providing quality labels—not on the intricacies of prompt engineering. Optimizer agents handle the complex process of exploring prompt variations and validating improvements, delivering reproducible results at scale.
          </p>
        }
        rightContent={
          <p className="text-lg text-muted-foreground">
            By combining evaluation metrics with intelligent agent workflows, we've automated the most time-consuming aspects of prompt optimization. The result is a systematic approach to improving LLM classifier performance that's both efficient and cost-effective.
          </p>
        }
      />

      <CTASection />
      <Footer />
    </Layout>
  )
} 
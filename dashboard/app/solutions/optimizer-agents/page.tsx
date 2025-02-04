import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { Button } from '@/components/ui/button'
import { ArrowRight } from 'lucide-react'
import { StandardSection } from '@/components/landing/StandardSection'
import BeforeAfterGauges from '@/components/BeforeAfterGauges'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { FrameSection } from '@/components/landing/FrameSection'

export default function OptimizerAgentsPage() {
  return (
    <Layout>
      <StandardSection
        headline={
          <span>
            <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text">Move The Needle</span> With <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">AI Agents</span> With <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text">No Code</span>
          </span>
        }
        headlinePosition="inline"
        variant="hero"
        layout="single"
        fullWidth
      >
        <div className="max-w-3xl mx-auto">
          <div className="space-y-8">
            <p className="text-xl text-muted-foreground text-center">
              Transform LLM-based classifiers from proof-of-concept to production-ready. Our optimizer agents automate the process of aligning prompts with your business needs, using a disciplined, scientific approach to prompt engineering.
            </p>
            <div className="flex justify-center">
              <Button size="lg" className="bg-primary text-white">
                Learn More
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </div>
          </div>
        </div>
      </StandardSection>

      <StandardSection
        headline="Automated Prompt Engineering"
        headlinePosition="top"
        leftContent={
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
        }
        rightContent={
          <div>
            <p className="text-xl text-muted-foreground">
              Optimizer agents use advanced techniques to explore the prompt space and find the best prompts for your use case. They automatically test variations and validate improvements, delivering reproducible results at scale.
            </p>
            <p className="text-xl text-muted-foreground mt-4">
              By combining evaluation metrics with intelligent agent workflows, we've automated the most time-consuming aspects of prompt optimization. The result is a systematic approach to improving LLM classifier performance that's both efficient and cost-effective.
            </p>
          </div>
        }
      />

      <FrameSection
        headline="Minimal Human Input Required"
        headlinePosition="top"
        layout="twoColumn"
        leftContent={
          <div className="space-y-4">
            <p className="text-xl text-muted-foreground">
              Your team's expertise stays focused on providing quality labels—not on the intricacies of prompt engineering. Optimizer agents handle the complex process of exploring prompt variations and validating improvements, delivering reproducible results at scale.
            </p>
          </div>
        }
        rightContent={
          <div className="space-y-4">
            <p className="text-xl text-muted-foreground">
              By combining evaluation metrics with intelligent agent workflows, we've automated the most time-consuming aspects of prompt optimization. The result is a systematic approach to improving LLM classifier performance that's both efficient and cost-effective.
            </p>
          </div>
        }
      />

      <div className="mt-24">
        <CTASection />
      </div>
      <Footer />
    </Layout>
  )
} 
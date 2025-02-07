"use client"

import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { PlatformFeatures } from '@/components/landing/PlatformFeatures'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { TaskCycleDemo } from '@/components/landing/TaskCycleDemo'
import { FrameSection } from '@/components/landing/FrameSection'
import MetricsGauges from '@/components/MetricsGauges'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'
import { StandardSection } from '@/components/landing/StandardSection'
import { Button } from '@/components/ui/button'
import { ArrowRight, Mail, Layout as LayoutIcon, Database, RefreshCw } from 'lucide-react'
import dynamic from 'next/dynamic'

const CLOCKWISE_SEQUENCE = [0, 1, 3, 2] // accuracy -> precision -> specificity -> sensitivity

const WorkflowClient = dynamic(
  () => import('@/components/workflow/base/workflow-base'),
  { ssr: false }
)

export default function PlatformPage() {
  const [rotationIndex, setRotationIndex] = React.useState(0)

  React.useEffect(() => {
    const interval = setInterval(() => {
      setRotationIndex(prev => (prev + 1) % CLOCKWISE_SEQUENCE.length)
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  // Map rotation index to actual gauge index for clockwise movement
  const selectedIndex = CLOCKWISE_SEQUENCE[rotationIndex]

  return (
    <Layout>
      <StandardSection
        headline="A Platform for Running AI Agents at Industrial Scale"
        headlinePosition="inline"
        variant="hero"
        useWordReveal={true}
        gradientWords={{
          "AI": { from: "primary", to: "accent" },
          "Agents": { from: "primary", to: "accent" },
          "Industrial": { from: "secondary", to: "accent" },
          "Scale": { from: "secondary", to: "accent" }
        }}
        leftContent={
          <>
            <p className="text-xl text-muted-foreground mb-8 w-full">
              Plexus is a serverless platform where your team can develop, test, and deploy AI agents without writing any code, and without worrying about the underlying infrastructure.
            </p>
            <p className="text-xl text-muted-foreground mb-8 w-full">
              Your team knows your business. Our team knows how to operate AI reliably at scale. Together, we can build and deploy solutions that transform your business.
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <Button size="lg" className="w-full sm:w-auto bg-primary text-white hover:bg-primary/90 text-lg font-semibold">
                Learn More
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </div>
          </>
        }
        rightContent={
          <div className="w-full max-w-[400px]">
            <WorkflowClient />
          </div>
        }
      />

      <StandardSection
        headline="Don't Just Guess — Guess and Test"
        headlinePosition="top"
        layout="twoColumn"
        leftContent={
          <MetricsGauges
            variant="detail"
            selectedIndex={selectedIndex}
            gauges={[
              { value: 92, label: 'Accuracy', segments: [ { start: 0, end: 60, color: 'var(--gauge-inviable)' }, { start: 60, end: 85, color: 'var(--gauge-converging)' }, { start: 85, end: 100, color: 'var(--gauge-great)' } ], backgroundColor: 'var(--gauge-background)' },
              { value: 91, label: 'Precision', segments: [ { start: 0, end: 60, color: 'var(--gauge-inviable)' }, { start: 60, end: 85, color: 'var(--gauge-converging)' }, { start: 85, end: 100, color: 'var(--gauge-great)' } ], backgroundColor: 'var(--gauge-background)' },
              { value: 95, label: 'Specificity', segments: [ { start: 0, end: 60, color: 'var(--gauge-inviable)' }, { start: 60, end: 85, color: 'var(--gauge-converging)' }, { start: 85, end: 100, color: 'var(--gauge-great)' } ], backgroundColor: 'var(--gauge-background)' },
              { value: 89, label: 'Sensitivity', segments: [ { start: 0, end: 60, color: 'var(--gauge-inviable)' }, { start: 60, end: 85, color: 'var(--gauge-converging)' }, { start: 85, end: 100, color: 'var(--gauge-great)' } ], backgroundColor: 'var(--gauge-background)' },
            ]}
          />
        }
        rightContent={
          <div>
            <p className="text-xl text-muted-foreground">
              You can't just write prompts and put them into production and hope they work, you need a way to evaluate them quantitatively to see if they meet your needs. You can't optimize a metric you're not measuring.
            </p>
            <p className="text-xl text-muted-foreground mt-4">
              Each use case demands its own success metrics: Is this a regulatory compliance question where we need high sensitivity? Do we need to use balanced accuracy because the data is unbalanced? Plexus gives you the gauges you need.
            </p>
          </div>
        }
      />

      <StandardSection
        headline="Your Team Knows Your Business"
        headlinePosition="top"
        fullWidth
      >
        <div className="max-w-3xl mx-auto text-center mb-12">
          <p className="text-xl text-muted-foreground">
            You need an efficient way to use your team's input to align AI 
            behavior &mdash; without depending on nerds who can write code.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          <div className="bg-card p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl">
            <Mail className="float-right ml-4 w-12 h-12 text-accent" />
            <h3 className="text-xl font-semibold mb-2 text-foreground">
              Mailbox folders
            </h3>
            <p className="text-muted-foreground">
              Train custom email classifiers by sorting messages into mailbox folders - your existing workflow becomes training data.
            </p>
          </div>
          <div className="bg-card p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl">
            <LayoutIcon className="float-right ml-4 w-12 h-12 text-accent" />
            <h3 className="text-xl font-semibold mb-2 text-foreground">
              Use our UI
            </h3>
            <p className="text-muted-foreground">
              Label items directly in the Plexus dashboard, contributing as much or as little as you can to improve classifier accuracy.
            </p>
          </div>
          <div className="bg-card p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl">
            <Database className="float-right ml-4 w-12 h-12 text-accent" />
            <h3 className="text-xl font-semibold mb-2 text-foreground">
              Custom integrations
            </h3>
            <p className="text-muted-foreground">
              We can incorporate labels from any data source or setup in your organization. Challenge us with your requirements.
            </p>
          </div>
          <div className="bg-card p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl">
            <RefreshCw className="float-right ml-4 w-12 h-12 text-accent" />
            <h3 className="text-xl font-semibold mb-2 text-foreground">
              Feedback loops
            </h3>
            <p className="text-muted-foreground">
              Review and correct agent decisions in real-time, creating a continuous cycle of improvement and refinement.
            </p>
          </div>
        </div>
      </StandardSection>

      <TaskCycleDemo />
      <PlatformFeatures />
      <CTASection />
      <Footer />
    </Layout>
  )
} 
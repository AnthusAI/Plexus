'use client'

import React from 'react'
import { Hero } from '@/components/landing/Hero'
import { Features } from '@/components/landing/Features'
import { LabelingStrategies } from '@/components/landing/LabelingStrategies'
import { UseCases } from '@/components/landing/UseCases'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Layout } from '@/components/landing/Layout'
import { Download, Brain, Workflow as WorkflowIcon } from 'lucide-react'
import dynamic from 'next/dynamic'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'
import MetricsGauges from '@/components/MetricsGauges'
import { StandardSection } from '@/components/landing/StandardSection'
import { FrameSection } from '@/components/landing/FrameSection'

const CLOCKWISE_SEQUENCE = [0, 1, 3, 2] // accuracy -> precision -> specificity -> sensitivity

const MultiModelWorkflowClient = dynamic(
  () => import('@/components/workflow/layouts/multi-model-workflow'),
  { ssr: false }
)

const MultiTypeWorkflowClient = dynamic(
  () => import('@/components/workflow/layouts/multi-type-workflow'),
  { ssr: false }
)

const ItemListWorkflowClient = dynamic(
  () => import('@/components/workflow/layouts/item-list-workflow'),
  { ssr: false }
)

export default function LandingPage() {
  const [selectedMetricIndex, setSelectedMetricIndex] = React.useState(0)
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
      <Hero />

      <StandardSection
        headline="Intelligence at Scale"
        headlinePosition="top"
        rightColumnAlign="middle"
        leftContent={<ItemListWorkflowClient />}
        rightContent={
          <p className="text-xl text-muted-foreground">
            Run a scorecard on each item of your data, with multiple scores per scorecard. Are your agents saying the right things? Are your inbound leads qualified? Classify, predict, extract, and act on your data.
          </p>
        }
      />

      <FrameSection
        headline="Use Any Model"
        headlinePosition="top"
        layout="twoColumn"
        leftContent={
          <>
            <p className="text-xl text-muted-foreground w-full">
              AI changes every week! Don't lock yourself into one solution. 
              Plexus is a workbench for applying any newfangled AI model to 
              solve your problems. Or simpler and cheaper ML models. Or 
              logical rules -- anything your solution requires.
            </p>
            <p className="text-xl text-muted-foreground w-full mt-4">
              OpenAI, Anthropic, Google, Deepseek, Azure, AWS Bedrock, Hugging Face, PyTorch, TensorFlow — 
              Plexus supports them all.
            </p>
          </>
        }
        rightContent={
          <div className="w-full max-w-[400px]">
            <MultiModelWorkflowClient />
          </div>
        }
      />

      <StandardSection
        headline="Don't Just Guess — Guess and Test"
        headlinePosition="top"
        leftContent={
          <MetricsGauges
            variant="detail"
            selectedIndex={selectedIndex}
            gauges={[
              {
                value: 92,
                label: 'Accuracy',
                segments: [
                  { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                  { start: 60, end: 85, color: 'var(--gauge-converging)' },
                  { start: 85, end: 100, color: 'var(--gauge-great)' }
                ],
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
                value: 95,
                label: 'Specificity',
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
              },
            ]}
          />
        }
        rightContent={
          <div>
            <p className="text-xl text-muted-foreground">
              You can't just write prompts and put them into production and hope they work, you need a way to evaluate them quantitatively to see if they meet your needs.  You can't optimize a metric you're not measuring.
            </p>
            <p className="text-xl text-muted-foreground mt-4">
              Each use case demands its own success metrics: Is this a regulatory compliance question where we need high sensitivity? Do we need to use balanced accuracy because the data is unbalanced? Plexus gives you the gauges you need.
            </p>
          </div>
        }
      />

      <FrameSection
        headline="Any Result Type"
        headlinePosition="top"
        layout="twoColumn"
        leftContent={
          <>
            <p className="text-xl text-muted-foreground w-full">
              Your answers should match your questions. Sometimes a simple yes/no will do, 
              other times you need a 5-star rating, a percentage score, or just a thumbs up. 
              Plexus gives you the flexibility to express your results in the format that makes sense 
              for your use case.
            </p>
            <p className="text-xl text-muted-foreground w-full mt-4">
              Binary classifiers, multi-class classifiers, scalar values, entity extraction, quote extraction, 
              and more.  The framework is flexible enough to support anything your solution requires.
            </p>
          </>
        }
        rightContent={
          <div className="w-full max-w-[400px]">
            <MultiTypeWorkflowClient />
          </div>
        }
      />

      <Features />

      <FrameSection
        headline="Organizational Intelligence"
        headlinePosition="top"
        layout="single"
      >
        <p className="text-2xl text-muted-foreground mb-12">
          Transform How Your Organization Handles Information
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
      </FrameSection>

      <UseCases />
      <CTASection />
      <Footer />
    </Layout>
  )
} 
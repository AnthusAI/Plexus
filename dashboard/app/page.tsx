'use client'

import React from 'react'
import { StandardSection } from '@/components/landing/StandardSection'
import { LabelingStrategies } from '@/components/landing/LabelingStrategies'
import { UseCases } from '@/components/landing/UseCases'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Layout } from '@/components/landing/Layout'
import { Download, Brain, Workflow as WorkflowIcon, ArrowRight, Cpu, FlaskRoundIcon as Flask, Cloud, Network } from 'lucide-react'
import dynamic from 'next/dynamic'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'
import MetricsGauges from '@/components/MetricsGauges'
import { Button } from '@/components/ui/button'

const CLOCKWISE_SEQUENCE = [0, 1, 3, 2] // accuracy -> precision -> specificity -> sensitivity

const MultiModelWorkflowClient = dynamic(
  () => import('@/components/workflow/layouts/multi-model-workflow'),
  { ssr: false }
)

const WorkflowClient = dynamic(
  () => import('@/components/workflow/base/workflow-base'),
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
      <StandardSection
        headline={
          <span>
            Run <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">AI Agents</span> Over <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text">Your Data</span> With <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text">No Code</span>
          </span>
        }
        headlinePosition="inline"
        variant="hero"
        leftContent={
          <>
            <p className="text-xl text-muted-foreground mb-8 w-full">
              Plexus is a battle-tested platform for building AI workflows that analyze streams of content and take action.
            </p>
            <p className="text-xl text-muted-foreground mb-8 w-full">
              Your team can use your data to set up step-by-step processes that automate information management. Without dealing with code development and deployment.
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
        headline="Intelligence at Scale"
        headlinePosition="top"
        rightColumnAlign="middle"
        leftContent={<ItemListWorkflowClient />}
        rightContent={
          <div>
            <p className="text-xl text-muted-foreground">
              Run a scorecard on each item of your data, with multiple scores per scorecard.
            </p>
            <p className="text-xl text-muted-foreground mt-4">
              Are your agents saying the right things? Are your inbound leads qualified?
            </p>
            <p className="text-xl text-muted-foreground mt-4">
              Classify, predict, extract, and act on your data.
            </p>
          </div>
        }
      />

      <StandardSection
        headline="Use Any Model"
        headlinePosition="top"
        layout="twoColumn"
        variant="framed"
        rightColumnAlign="middle"
        leftContent={
          <p className="text-xl text-muted-foreground">
            AI changes every week! Don't lock yourself into one solution. 
            Plexus is a workbench for applying any newfangled AI model to 
            solve your problems. Or simpler and cheaper ML models. Or 
            logical rules -- anything your solution requires.
            {"\n\n"}
            OpenAI, Anthropic, Google, Deepseek, Azure, AWS Bedrock, Hugging Face, PyTorch, TensorFlow — 
            Plexus supports them all.
          </p>
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
              You can't just write prompts and put them into production and hope they work, you need a way to evaluate them quantitatively to see if they meet your needs. You can't optimize a metric you're not measuring.
            </p>
            <p className="text-xl text-muted-foreground mt-4">
              Each use case demands its own success metrics: Is this a regulatory compliance question where we need high sensitivity? Do we need to use balanced accuracy because the data is unbalanced? Plexus gives you the gauges you need.
            </p>
          </div>
        }
      />

      <StandardSection
        headline="Any Result Type"
        headlinePosition="top"
        layout="twoColumn"
        variant="framed"
        rightColumnAlign="middle"
        leftContent={
          <p className="text-xl text-muted-foreground">
            Your answers should match your questions. Sometimes a simple yes/no will do, 
            other times you need a 5-star rating, a percentage score, or just a thumbs up. 
            Plexus gives you the flexibility to express your results in the format that makes sense 
            for your use case.
            {"\n\n"}
            Binary classifiers, multi-class classifiers, scalar values, entity extraction, quote extraction, 
            and more. The framework is flexible enough to support anything your solution requires.
          </p>
        }
        rightContent={
          <div className="w-full max-w-[400px]">
            <MultiTypeWorkflowClient />
          </div>
        }
      />

      <StandardSection
        headline="Powerful Features for Agent Orchestration"
        headlinePosition="top"
        fullWidth
      >
        <div className="max-w-3xl mx-auto text-center mb-12">
          <p className="text-2xl text-muted-foreground mb-12">
            Built by practitioners on the front lines of AI deployment. Our features 
            evolve as rapidly as AI itself, delivering battle-tested tools that 
            transform cutting-edge capabilities into real business value.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          <div className="bg-card p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl">
            <Cpu className="float-right ml-4 w-12 h-12 text-accent" />
            <h3 className="text-xl font-semibold mb-2 text-foreground">
              Multi-model
            </h3>
            <p className="text-muted-foreground">
              Use any AI/ML model, from GPT-4 or Claude, to your own fine-tuned local Llama, to custom BERT-based classifiers.
            </p>
          </div>
          <div className="bg-card p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl">
            <Flask className="float-right ml-4 w-12 h-12 text-accent" />
            <h3 className="text-xl font-semibold mb-2 text-foreground">
              Lab workflow
            </h3>
            <p className="text-muted-foreground">
              Create and align your own custom classifiers using sophisticated tools for analyzing datasets and evaluating results.
            </p>
          </div>
          <div className="bg-card p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl">
            <Cloud className="float-right ml-4 w-12 h-12 text-accent" />
            <h3 className="text-xl font-semibold mb-2 text-foreground">
              Serverless
            </h3>
            <p className="text-muted-foreground">
              Plexus is a lightning-fast, fully DevOps / IaC / NoSQL project that doesn't depend on servers or databases.
            </p>
          </div>
          <div className="bg-card p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl">
            <Network className="float-right ml-4 w-12 h-12 text-accent" />
            <h3 className="text-xl font-semibold mb-2 text-foreground">
              Task dispatch
            </h3>
            <p className="text-muted-foreground">
              Connect any node as a worker for running agents, evaluations, or reports, from AWS to Azure to local computers.
            </p>
          </div>
        </div>
      </StandardSection>

      <UseCases />
      <CTASection />
      <Footer />
    </Layout>
  )
} 
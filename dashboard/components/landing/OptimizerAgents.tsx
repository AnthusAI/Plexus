import React from 'react'
import { Layout } from './Layout'
import { Button } from '@/components/ui/button'
import { ArrowRight } from 'lucide-react'
import { StandardSection } from './StandardSection'
import { FrameSection } from './FrameSection'

export default function OptimizerAgents() {
  return (
    <Layout>
      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-24 md:py-32 px-4 md:px-8">
              <div className="max-w-3xl mx-auto text-center">
                <h1 className="text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-8 text-foreground">
                  Self-Improving AI Classification
                </h1>
                <p className="text-xl text-muted-foreground">
                  Your AI classifiers can now learn from their mistakes and evolve.
                  Optimizer agents analyze results, identify patterns, and automatically
                  enhance performance.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <StandardSection
        headline="Understanding Classification Results"
        headlinePosition="inline"
        leftContent={
          <p className="text-lg text-muted-foreground">
            Optimizer agents dive deep into evaluation data, examining where 
            classifiers succeed and fail. They identify patterns in 
            misclassifications and analyze the root causes of errors.
          </p>
        }
        rightContent={
          <div className="bg-muted aspect-square rounded-lg">
            <div className="h-full flex items-center justify-center text-muted-foreground">
              Analysis Process Diagram
            </div>
          </div>
        }
      />

      <FrameSection
        headline="Intelligent Prompt Evolution"
        layout="twoColumn"
        leftContent={
          <div className="bg-muted aspect-square rounded-lg">
            <div className="h-full flex items-center justify-center text-muted-foreground">
              Optimization Cycle Diagram
            </div>
          </div>
        }
        rightContent={
          <div className="space-y-6">
            <p className="text-lg text-muted-foreground">
              When opportunities for improvement are found, optimizer agents craft 
              and test refined prompts. Each iteration is validated against your 
              evaluation data, ensuring real performance gains.
            </p>
          </div>
        }
      />

      <StandardSection
        headline="Targeted Performance Improvements"
        headlinePosition="inline"
        leftContent={
          <p className="text-lg text-muted-foreground">
            Different use cases demand different optimization goals. Compliance 
            screening might prioritize sensitivity, while content sorting needs 
            specificity. Optimizer agents adapt their strategies to your metrics.
          </p>
        }
        rightContent={
          <div className="bg-muted aspect-square rounded-lg">
            <div className="h-full flex items-center justify-center text-muted-foreground">
              Performance Metrics Diagram
            </div>
          </div>
        }
      />

      <FrameSection
        headline="Ready to Evolve Your AI?"
        layout="single"
      >
        <div className="max-w-2xl mx-auto text-center">
          <p className="text-lg text-muted-foreground mb-8">
            Let your classifiers learn and improve automatically. Start using 
            optimizer agents to enhance your AI workflows today.
          </p>
          <Button size="lg" className="bg-primary text-white">
            Get Started
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </FrameSection>
    </Layout>
  )
} 
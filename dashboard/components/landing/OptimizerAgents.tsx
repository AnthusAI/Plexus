import React from 'react'
import { Layout } from './Layout'
import { Button } from '@/components/ui/button'
import { ArrowRight } from 'lucide-react'

export default function OptimizerAgents() {
  return (
    <Layout>
      <div className="container mx-auto px-4 max-w-7xl py-16">
        {/* Hero Section */}
        <div className="max-w-3xl mx-auto text-center mb-24">
          <h1 className="text-5xl font-bold tracking-tight mb-6">
            Self-Improving AI Classification
          </h1>
          <p className="text-xl text-muted-foreground">
            Your AI classifiers can now learn from their mistakes and evolve.
            Optimizer agents analyze results, identify patterns, and automatically
            enhance performance.
          </p>
        </div>

        {/* Analysis Section */}
        <div className="grid md:grid-cols-2 gap-16 items-center mb-32">
          <div className="space-y-6">
            <h2 className="text-3xl font-bold tracking-tight">
              Understanding Classification Results
            </h2>
            <p className="text-lg text-muted-foreground">
              Optimizer agents dive deep into evaluation data, examining where 
              classifiers succeed and fail. They identify patterns in 
              misclassifications and analyze the root causes of errors.
            </p>
          </div>
          <div className="bg-muted aspect-square rounded-lg">
            {/* Placeholder for diagram showing analysis process */}
            <div className="h-full flex items-center justify-center text-muted-foreground">
              Analysis Process Diagram
            </div>
          </div>
        </div>

        {/* Optimization Section */}
        <div className="grid md:grid-cols-2 gap-16 items-center mb-32">
          <div className="order-last md:order-first bg-muted aspect-square rounded-lg">
            {/* Placeholder for diagram showing optimization cycle */}
            <div className="h-full flex items-center justify-center text-muted-foreground">
              Optimization Cycle Diagram
            </div>
          </div>
          <div className="space-y-6">
            <h2 className="text-3xl font-bold tracking-tight">
              Intelligent Prompt Evolution
            </h2>
            <p className="text-lg text-muted-foreground">
              When opportunities for improvement are found, optimizer agents craft 
              and test refined prompts. Each iteration is validated against your 
              evaluation data, ensuring real performance gains.
            </p>
          </div>
        </div>

        {/* Metrics Section */}
        <div className="grid md:grid-cols-2 gap-16 items-center mb-32">
          <div className="space-y-6">
            <h2 className="text-3xl font-bold tracking-tight">
              Targeted Performance Improvements
            </h2>
            <p className="text-lg text-muted-foreground">
              Different use cases demand different optimization goals. Compliance 
              screening might prioritize sensitivity, while content sorting needs 
              specificity. Optimizer agents adapt their strategies to your metrics.
            </p>
          </div>
          <div className="bg-muted aspect-square rounded-lg">
            {/* Placeholder for diagram showing metrics and goals */}
            <div className="h-full flex items-center justify-center text-muted-foreground">
              Performance Metrics Diagram
            </div>
          </div>
        </div>

        {/* CTA Section */}
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl font-bold tracking-tight mb-6">
            Ready to Evolve Your AI?
          </h2>
          <p className="text-lg text-muted-foreground mb-8">
            Let your classifiers learn and improve automatically. Start using 
            optimizer agents to enhance your AI workflows today.
          </p>
          <Button size="lg" className="bg-primary text-white">
            Get Started
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </div>
    </Layout>
  )
} 
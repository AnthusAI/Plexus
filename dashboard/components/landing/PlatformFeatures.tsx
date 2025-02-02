import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { 
  Cpu,
  Network, 
  FlaskConical,
  RefreshCw,
  Blocks,
  Cloud,
  Gauge,
  GitMerge,
} from 'lucide-react'

const features = [
  {
    title: "Agent Orchestration",
    description: "Direct AI agents to analyze and act on streams of content in real-time, from call transcripts to chat logs",
    icon: Cpu
  },
  {
    title: "Custom Scorecards",
    description: "Build your own scores beyond basic sentiment analysis - create custom metrics that matter to your business",
    icon: Blocks
  },
  {
    title: "Evaluation Framework",
    description: "Rigorously test and validate your classifiers with sophisticated tools for analyzing performance",
    icon: FlaskConical
  },
  {
    title: "Continuous Learning",
    description: "Automatically incorporate new labeled data to keep your scorecards aligned with evolving business needs",
    icon: RefreshCw
  }
]

const capabilities = [
  {
    title: "Multi-Model Toolkit",
    description: "Use any model from any provider - OpenAI, Anthropic, Llama, Mistral, Deepseek, or your own custom models",
    icon: Network
  },
  {
    title: "Distributed Workers",
    description: "Dispatch work to any cloud provider or on-premises infrastructure with flexible worker deployment",
    icon: Cloud
  },
  {
    title: "Realtime Dashboard",
    description: "Keep your team coordinated with our lightning-fast, serverless, collaborative interface",
    icon: Gauge
  },
  {
    title: "Multi-Step Inference",
    description: "Combine LLMs, ML models, semantic search, and custom APIs into sophisticated scoring pipelines",
    icon: GitMerge
  }
]

export const PlatformFeatures = () => {
  return (
    <>
      <section className="py-20">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold mb-12 text-center text-foreground">
            Platform Features
          </h2>
          <div className="grid md:grid-cols-2 gap-8">
            {features.map((feature, index) => {
              const Icon = feature.icon
              return (
                <Card key={index} className="border-none shadow-lg hover:shadow-xl 
                                          transition-shadow duration-300">
                  <CardContent className="p-6">
                    <Icon className="h-12 w-12 mb-4 text-accent" />
                    <h3 className="text-xl font-semibold mb-2 text-foreground">
                      {feature.title}
                    </h3>
                    <p className="text-muted-foreground">
                      {feature.description}
                    </p>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>
      </section>

      <section className="py-20 bg-accent/5">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold mb-12 text-center text-foreground">
            Advanced Capabilities
          </h2>
          <div className="grid md:grid-cols-2 gap-8">
            {capabilities.map((capability, index) => {
              const Icon = capability.icon
              return (
                <Card key={index} className="border-none shadow-lg">
                  <CardContent className="p-6">
                    <Icon className="h-12 w-12 mb-4 text-accent" />
                    <h3 className="text-xl font-semibold mb-2 text-foreground">
                      {capability.title}
                    </h3>
                    <p className="text-muted-foreground">
                      {capability.description}
                    </p>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>
      </section>
    </>
  )
} 
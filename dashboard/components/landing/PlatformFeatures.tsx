import React from 'react'
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
import { FrameSection } from '@/components/landing/FrameSection'
import { StandardSection } from '@/components/landing/StandardSection'
import { FeatureCard } from './FeatureCard'

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
      <StandardSection
        headline="Platform Features"
        headlinePosition="top"
        fullWidth
      >
        <div className="max-w-4xl mx-auto">
          <div className="grid md:grid-cols-2 gap-8">
            {features.map((feature, index) => (
              <FeatureCard
                key={index}
                title={feature.title}
                description={feature.description}
                icon={feature.icon}
              />
            ))}
          </div>
        </div>
      </StandardSection>

      <FrameSection
        headline="Multi-Model Toolkit"
        headlinePosition="top"
        fullWidth
      >
        <div className="max-w-4xl mx-auto">
          <div className="grid md:grid-cols-2 gap-8">
            {capabilities.map((capability, index) => (
              <FeatureCard
                key={index}
                title={capability.title}
                description={capability.description}
                icon={capability.icon}
              />
            ))}
          </div>
        </div>
      </FrameSection>
    </>
  )
} 
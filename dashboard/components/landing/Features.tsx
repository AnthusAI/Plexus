import React from 'react'
import { Cpu, FlaskRoundIcon as Flask, Cloud, Network } from 'lucide-react'
import { StandardSection } from '@/components/landing/StandardSection'

const features = [
  {
    title: "Multi-model",
    description: "Use any AI/ML model, from GPT-4 or Claude, to your own fine-tuned local Llama, to custom BERT-based classifiers.",
    icon: Cpu
  },
  {
    title: "Lab workflow",
    description: "Create and align your own custom classifiers using sophisticated tools for analyzing datasets and evaluating results.",
    icon: Flask
  },
  {
    title: "Serverless",
    description: "Plexus is a lightning-fast, fully DevOps / IaC / NoSQL project that doesn't depend on servers or databases.",
    icon: Cloud
  },
  {
    title: "Task dispatch",
    description: "Connect any node as a worker for running agents, evaluations, or reports, from AWS to Azure to local computers.",
    icon: Network
  }
]

export const Features = () => {
  return (
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
        {features.map((feature, index) => (
          <div key={index} 
               className="bg-card p-6 rounded-lg shadow-md 
                         transition-all duration-300 hover:shadow-xl">
            <feature.icon className="float-right ml-4 w-12 h-12 text-accent" />
            <h3 className="text-xl font-semibold mb-2 text-foreground">
              {feature.title}
            </h3>
            <p className="text-muted-foreground">
              {feature.description}
            </p>
          </div>
        ))}
      </div>
    </StandardSection>
  )
}


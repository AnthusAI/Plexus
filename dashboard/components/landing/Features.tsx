import React from 'react'
import { Cpu, FlaskRoundIcon as Flask, Cloud, Network } from 'lucide-react'

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
    <section className="py-20 bg-background">
      <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className="py-4">
          <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
            <div className="max-w-3xl mx-auto text-center mb-12">
              <h2 className="text-4xl md:text-5xl font-bold mb-8 text-foreground">
                Powerful Features for Agent Orchestration
              </h2>
              <p className="text-2xl text-muted-foreground mb-12">
                Built by practitioners on the front lines of AI deployment, our features 
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
          </div>
        </div>
      </div>
    </section>
  )
}


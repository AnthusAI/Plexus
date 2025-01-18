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
    <section className="py-20 bg-gray-50">
      <div className="container mx-auto px-4">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">Powerful Features for Agent Orchestration</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {features.map((feature, index) => (
            <div key={index} className="bg-white p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl">
              <feature.icon className="w-12 h-12 mb-4 text-fuchsia-500" />
              <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
              <p className="text-gray-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}


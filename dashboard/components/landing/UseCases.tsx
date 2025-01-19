import React from 'react'
import { Mail, Layout, Database, RefreshCw } from 'lucide-react'

const useCases = [
  {
    title: "Mailbox folders",
    description: "Train custom email classifiers by sorting messages into mailbox folders - your existing workflow becomes training data.",
    icon: Mail
  },
  {
    title: "Use our UI",
    description: "Label items directly in the Plexus dashboard, contributing as much or as little as you can to improve classifier accuracy.",
    icon: Layout
  },
  {
    title: "Custom integrations",
    description: "We can incorporate labels from any data source or setup in your organization. Challenge us with your requirements.",
    icon: Database
  },
  {
    title: "Feedback loops",
    description: "Review and correct agent decisions in real-time, creating a continuous cycle of improvement and refinement.",
    icon: RefreshCw
  }
]

export const UseCases = () => {
  return (
    <section className="py-20 bg-background">
      <div className="container mx-auto px-4">
        <div className="max-w-3xl mx-auto text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4 text-foreground">
            Your Team Knows Your Business
          </h2>
          <p className="text-xl text-muted-foreground">
            You need an efficient way to use your team's input to align AI 
            behavior -- without depending on nerds who can write code.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {useCases.map((useCase, index) => (
            <div key={index} 
                 className="bg-card p-6 rounded-lg shadow-md 
                           transition-all duration-300 hover:shadow-xl">
              <useCase.icon className="float-right ml-4 w-12 h-12 text-accent" />
              <h3 className="text-xl font-semibold mb-2 text-foreground">
                {useCase.title}
              </h3>
              <p className="text-muted-foreground">
                {useCase.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
} 
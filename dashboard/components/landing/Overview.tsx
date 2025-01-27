import React from 'react'
import { Download, Brain, Workflow as WorkflowIcon } from 'lucide-react'
import WorkflowIllustration from './workflow'

export const Overview = () => {
  return (
    <section className="py-20 bg-background">
      <div className="container mx-auto px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold mb-8 text-foreground 
                       bg-gradient-to-r from-accent to-accent-foreground 
                       bg-clip-text text-transparent">
            Intelligence at Scale
          </h2>
          <p className="text-2xl font-semibold mb-12 text-foreground">
            Transform how your organization handles information
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
        </div>
      </div>

      <div className="container mx-auto px-4 mt-20">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div className="w-full max-w-xl">
            <WorkflowIllustration />
          </div>
          <div>
            <h3 className="text-3xl font-bold mb-6 text-foreground">
              Intelligent Workflow Orchestration
            </h3>
            <p className="text-xl text-muted-foreground">
              Our platform seamlessly coordinates complex workflows, 
              intelligently routing tasks and data through your organization. 
              From initial data ingestion to final actions, every step is 
              optimized for efficiency and accuracy, ensuring your processes 
              run smoothly at any scale.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
} 
import React from 'react'
import { Layout } from './Layout'

export const CallCenterQA = () => {
  return (
    <Layout>
      <section className="py-20 bg-background">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-4xl md:text-5xl font-bold mb-8 text-foreground 
                         bg-gradient-to-r from-accent to-accent-foreground 
                         bg-clip-text text-transparent">
              Call Center Quality Assurance
            </h1>
            <p className="text-2xl text-muted-foreground mb-12">
              Transform your call center operations with AI-powered quality 
              assurance and performance analytics
            </p>
          </div>
        </div>
      </section>

      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold mb-8 text-foreground">
              Key Benefits
            </h2>
            {/* Benefits content will go here */}
          </div>
        </div>
      </section>

      <section className="py-20 bg-accent/5">
        <div className="container mx-auto px-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold mb-8 text-foreground">
              How It Works
            </h2>
            {/* Process explanation will go here */}
          </div>
        </div>
      </section>
    </Layout>
  )
} 
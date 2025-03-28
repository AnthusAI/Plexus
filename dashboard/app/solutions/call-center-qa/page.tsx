'use client'

import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { StandardSection } from '@/components/landing/StandardSection'
import { FrameSection } from '@/components/landing/FrameSection'
import { Button } from '@/components/ui/button'
import { ArrowRight, Bot, GraduationCap, DollarSign, ArrowUpWideNarrow } from 'lucide-react'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'

export default function CallCenterQAPage() {
  return (
    <Layout>
      <StandardSection
        headline="Monitor Calls With AI Agents With No Code"
        headlinePosition="inline"
        variant="hero"
        useWordReveal={true}
        gradientWords={{
          "Monitor": { from: "secondary", to: "accent" },
          "Calls": { from: "secondary", to: "accent" },
          "AI": { from: "primary", to: "accent" },
          "Agents": { from: "primary", to: "accent" },
          "No": { from: "primary", to: "accent" },
          "Code": { from: "primary", to: "accent" }
        }}
        leftContent={
          <>
            <p className="text-xl text-muted-foreground mb-8 w-full">
              Replace expensive manual call quality assessments with AI-driven automation.
              Save the cost of full-time QA staff while improving evaluation coverage and consistency.
            </p>
            <p className="text-xl text-muted-foreground mb-8 w-full">
              We know how to operate AI agents at scale. We've built a platform that enables you to monitor calls with with no code.
            </p>
            <p className="text-xl text-muted-foreground mb-8 w-full">
              Humans still need to steer it, and your team knows best how to do that. Plexus gives your team the tools they need to make it happen.
            </p>
          </>
        }
        rightContent={
          <div className="w-full max-w-[400px]">
            <ItemListWorkflow 
              allowedMediaTypes={["audio"]} 
              allowedShapes={["circle"]}
              resultTypes={[
                { type: "check" },
                { type: "check" },
                { type: "check" },
                { type: "check" }
              ]}
            />
          </div>
        }
      />

      <StandardSection
        headline="Transform Your QA Process"
        headlinePosition="top"
        fullWidth
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <DollarSign className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Reduce Manual QA</h3>
            <p className="text-muted-foreground">
              Automate evaluations with AI to save the expense of full-time QA staff while increasing coverage.
            </p>
          </div>
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <GraduationCap className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Accelerate Agent Growth</h3>
            <p className="text-muted-foreground">
              Help new hires reach full productivity faster with AI-powered training insights and feedback.
            </p>
          </div>
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <ArrowUpWideNarrow className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Maximize Call Coverage</h3>
            <p className="text-muted-foreground">
              Monitor and analyze 100% of customer interactions with AI-powered quality assurance at scale.
            </p>
          </div>
        </div>
      </StandardSection>

      <FrameSection
        headline="Don't get locked into one AI vendor"
        headlinePosition="top"
        layout="twoColumn"
        leftContent={
          <div className="w-full max-w-[400px] mx-auto">
            <ItemListWorkflow 
              allowedMediaTypes={["audio"]} 
              fixedShapeSequence={["square", "pill", "triangle", "circle"]}
              resultTypes={[
                { 
                  type: "text", 
                  values: [
                    { text: "yes", color: "true" },
                    { text: "yes", color: "true" },
                    { text: "yes", color: "true" },
                    { text: "yes", color: "true" },
                    { text: "yes", color: "true" },
                    { text: "yes", color: "true" },
                    { text: "yes", color: "true" },
                    { text: "yes", color: "true" },
                    { text: "yes", color: "true" },
                    { text: "no", color: "false" }
                  ]
                },
                { 
                  type: "text",
                  values: [
                    { text: "Skip", color: "muted-foreground", width: 2.5 },
                    { text: "Accept", color: "true", width: 2.5 },
                    { text: "Reject", color: "false", width: 2.5 },
                    { text: "Report", color: "false", width: 2.5 }
                  ]
                },
                { 
                  type: "check"
                },
                { 
                  type: "boolean",
                  booleanRatio: 0.9
                }
              ]}
            />
          </div>
        }
        rightContent={
          <div className="space-y-4">
            <p className="text-xl text-muted-foreground">
              The AI landscape evolves weekly. What works today might be outdated tomorrow. Plexus gives you the flexibility to integrate any AI model - whether it's OpenAI, Anthropic, Google, or Deepseek - without being locked into a single vendor's ecosystem.
            </p>
            <p className="text-xl text-muted-foreground">
              Build your solution your way. Use the latest GPT-4 model, fine-tune Claude for your specific needs, or deploy your own custom models. Plexus handles the infrastructure, scaling, and monitoring, so you can focus on delivering value to your customers.
            </p>
          </div>
        }
      />

      <StandardSection
        headline="Enterprise-Ready Integration"
        headlinePosition="top"
        fullWidth
      >
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-xl text-muted-foreground mb-6">
            Connect Plexus to your existing systems to automate actions based on call analysis. Whether you need to update tickets in ServiceNow, create tasks in Salesforce, or trigger custom workflows in your internal tools, we can integrate with your stack.
          </p>
          <p className="text-xl text-muted-foreground">
            Ready to work with your VoIP provider of choice, including RingCentral, Five9, Twilio, and Microsoft Teams. We've built certified integrations with major enterprise platforms and can adapt to your specific infrastructure needs.
          </p>
        </div>
      </StandardSection>

      <CTASection />
      <Footer />
    </Layout>
  )
} 
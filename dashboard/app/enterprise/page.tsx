'use client'

import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Button } from '@/components/ui/button'
import { ArrowRight, Shield, Users, Building2, Lock } from 'lucide-react'
import { StandardSection } from '@/components/landing/StandardSection'
import { FrameSection } from '@/components/landing/FrameSection'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'
import { FeatureCard } from '@/components/landing/FeatureCard'

export default function EnterprisePage() {
  return (
    <Layout>
      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
              <div className="flex flex-col xl:flex-row gap-8">
                <div className="flex-1 min-w-0 xl:w-[calc(50%-2rem)]">
                  <h1 className="text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-6 md:mb-12 leading-tight text-center md:text-center xl:text-left">
                    <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">Enterprise-grade</span> AI <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text whitespace-nowrap">infrastructure</span>
                  </h1>
                  <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                    <div className="w-full md:w-1/2 xl:w-full flex flex-col items-center md:items-start text-center md:text-left md:justify-center">
                      <p className="text-xl text-muted-foreground mb-8 text-justify w-full">
                        Deploy AI with confidence using our enterprise-ready platform. Built for security, scalability, and compliance from the ground up.
                      </p>
                      <p className="text-xl text-muted-foreground mb-8 text-justify w-full">
                        Get dedicated support, custom integrations, and advanced security features to meet your organization's unique needs.
                      </p>
                      <div className="flex justify-center xl:justify-start">
                        <Button size="lg" className="bg-primary text-white">
                          Contact Sales
                          <ArrowRight className="ml-2 h-5 w-5" />
                        </Button>
                      </div>
                    </div>
                    <div className="w-full md:w-1/2 xl:hidden flex justify-center md:justify-end items-center">
                      <div className="w-full max-w-[400px]">
                        <ItemListWorkflow 
                          fixedShapeSequence={["square", "hexagon", "circle", "triangle"]}
                          resultTypes={[
                            { type: "check" },
                            { type: "check" },
                            { type: "check" },
                            { type: "check" }
                          ]}
                        />
                      </div>
                    </div>
                  </div>
                </div>
                <div className="hidden xl:flex flex-1 min-w-0 xl:w-[calc(50%-2rem)] justify-center md:justify-end items-center">
                  <div className="w-full max-w-[400px]">
                    <ItemListWorkflow 
                      fixedShapeSequence={["square", "hexagon", "circle", "triangle"]}
                      resultTypes={[
                        { type: "check" },
                        { type: "check" },
                        { type: "check" },
                        { type: "check" }
                      ]}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <StandardSection
        headline="Enterprise Features"
        headlinePosition="top"
        fullWidth
      >
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8 max-w-6xl mx-auto">
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <Shield className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Enterprise Security</h3>
            <p className="text-muted-foreground">
              SOC 2 Type II certified with end-to-end encryption and advanced security controls.
            </p>
          </div>
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <Users className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Team Management</h3>
            <p className="text-muted-foreground">
              Advanced user roles, permissions, and audit logs for complete control.
            </p>
          </div>
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <Building2 className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Custom Deployment</h3>
            <p className="text-muted-foreground">
              On-premise or dedicated cloud deployment options with SLA guarantees.
            </p>
          </div>
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <Lock className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Data Privacy</h3>
            <p className="text-muted-foreground">
              GDPR and HIPAA compliant with data residency options.
            </p>
          </div>
        </div>
      </StandardSection>

      <FrameSection
        headline="Enterprise Support"
        layout="twoColumn"
        leftContent={
          <div className="space-y-6">
            <p className="text-xl text-muted-foreground text-justify">
              Get dedicated support from our team of AI experts. We'll help you design, implement, and optimize your AI workflows.
            </p>
            <ul className="space-y-4 text-lg text-muted-foreground">
              <li>• Dedicated account manager</li>
              <li>• 24/7 priority support</li>
              <li>• Custom integration assistance</li>
              <li>• Training and onboarding</li>
              <li>• Quarterly business reviews</li>
            </ul>
          </div>
        }
        rightContent={
          <div className="w-full max-w-[400px]">
            <ItemListWorkflow 
              fixedShapeSequence={["circle", "square", "triangle", "hexagon"]}
              resultTypes={[
                { type: "text", values: [{ text: "Support", color: "true" }] },
                { type: "text", values: [{ text: "Training", color: "true" }] },
                { type: "text", values: [{ text: "Review", color: "true" }] },
                { type: "text", values: [{ text: "Success", color: "true" }] }
              ]}
            />
          </div>
        }
      />

      <CTASection />
      <Footer />
    </Layout>
  )
} 
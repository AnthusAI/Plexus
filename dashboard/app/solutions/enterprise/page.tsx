'use client'

import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Button } from '@/components/ui/button'
import { ArrowRight, Shield, Users, Building2, Lock } from 'lucide-react'
import { StandardSection } from '@/components/landing/StandardSection'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'
import { FeatureCard } from '@/components/landing/FeatureCard'

export default function EnterprisePage() {
  return (
    <Layout>
      <StandardSection
        headline={
          <span>
            <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">Enterprise-Grade</span> AI Infrastructure
          </span>
        }
        headlinePosition="inline"
        variant="hero"
        layout="single"
        fullWidth
      >
        <div className="max-w-3xl mx-auto">
          <div className="space-y-8">
            <p className="text-xl text-muted-foreground text-center">
              Deploy AI with confidence using our enterprise-ready platform. Built for security, scalability, and compliance from the ground up.
            </p>
            <p className="text-xl text-muted-foreground text-center">
              Get dedicated support, custom integrations, and advanced security features to meet your organization's unique needs.
            </p>
            <div className="flex justify-center">
              <Button size="lg" className="bg-primary text-white">
                Contact Sales
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </div>
          </div>
        </div>
      </StandardSection>

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
            <h3 className="text-xl font-semibold mb-2">Enterprise-grade Security & Privacy</h3>
            <p className="text-muted-foreground">
              SOC 2, GDPR, and CCPA compliant with data residency option.
            </p>
          </div>
        </div>
      </StandardSection>

      <StandardSection
        headline="Built on AWS Well-Architected Framework"
        headlinePosition="top"
        layout="single"
        variant="framed"
      >
        <div className="space-y-12 max-w-6xl mx-auto">
          <p className="text-xl text-muted-foreground text-center max-w-4xl mx-auto">
            Plexus is engineered following AWS Well-Architected Framework principles, delivering enterprise-grade reliability, security, and operational excellence through a fully serverless architecture.
          </p>
          
          <div className="grid md:grid-cols-2 gap-12">
            <div className="space-y-4">
              <div className="space-y-2">
                <h3 className="text-xl font-semibold">Infrastructure as Code</h3>
                <p className="text-lg text-muted-foreground">
                  Our entire infrastructure is defined and managed through code, enabling consistent deployments and automated scaling across all environments.
                </p>
              </div>
              <div className="space-y-2">
                <h3 className="text-xl font-semibold">DevOps Best Practices</h3>
                <p className="text-lg text-muted-foreground">
                  Continuous integration and deployment pipelines ensure reliable updates and zero-downtime deployments.
                </p>
              </div>
              <div className="space-y-2">
                <h3 className="text-xl font-semibold">Serverless Architecture</h3>
                <p className="text-lg text-muted-foreground">
                  Built entirely on AWS serverless technologies, providing automatic scaling, high availability, and cost optimization.
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="text-xl font-semibold">Well-Architected Pillars</h3>
              <ul className="space-y-3 text-lg text-muted-foreground">
                <li>• Operational Excellence through automated operations</li>
                <li>• Security with fine-grained IAM and encryption at rest/transit</li>
                <li>• Reliability with multi-AZ deployments</li>
                <li>• Performance Efficiency via serverless auto-scaling</li>
                <li>• Cost Optimization through pay-per-use model</li>
                <li>• Sustainability using efficient resource allocation</li>
              </ul>
            </div>
          </div>
        </div>
      </StandardSection>

      <StandardSection
        headline="Enterprise Support"
        headlinePosition="top"
        leftContent={
          <div className="space-y-6 max-w-3xl mx-auto">
            <p className="text-xl text-muted-foreground">
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
      />

      <CTASection />
      <Footer />
    </Layout>
  )
} 
'use client'

import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Button } from '@/components/ui/button'
import { ArrowRight, BookOpen, GraduationCap, Video, MessageSquare } from 'lucide-react'
import { StandardSection } from '@/components/landing/StandardSection'
import { FeatureCard } from '@/components/landing/FeatureCard'
import Link from 'next/link'

export default function ResourcesPage() {
  return (
    <Layout>
      <StandardSection
        headline={
          <span>
            <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text">Learn to Build</span> With <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">AI Agents</span>
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
              Explore our comprehensive resources to master AI agent development. From getting started guides to advanced tutorials.
            </p>
            <p className="text-xl text-muted-foreground text-center">
              Join our community of developers and AI practitioners to share knowledge and best practices.
            </p>
            <div className="flex justify-center">
              <Button size="lg" className="bg-primary text-white" asChild>
                <Link href="/documentation">
                  Browse Documentation
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </StandardSection>

      <StandardSection
        headline="Learning Resources"
        headlinePosition="top"
        fullWidth
      >
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8 max-w-6xl mx-auto">
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <BookOpen className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Documentation</h3>
            <p className="text-muted-foreground">
              Comprehensive guides and API references for building with Plexus.
            </p>
          </div>
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <GraduationCap className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Tutorials</h3>
            <p className="text-muted-foreground">
              Step-by-step tutorials for common AI agent development scenarios.
            </p>
          </div>
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <Video className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Video Guides</h3>
            <p className="text-muted-foreground">
              Watch video tutorials and webinars from our team of experts.
            </p>
          </div>
          <div className="flex flex-col items-center text-center p-6 rounded-lg transition-all duration-300 hover:bg-accent/5">
            <MessageSquare className="w-16 h-16 mb-6 text-accent" />
            <h3 className="text-xl font-semibold mb-2">Community</h3>
            <p className="text-muted-foreground">
              Join our Discord community to connect with other developers.
            </p>
          </div>
        </div>
      </StandardSection>

      <StandardSection
        headline="Latest Resources"
        headlinePosition="top"
        layout="single"
        variant="framed"
      >
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          <div className="space-y-4">
            <h3 className="text-2xl font-semibold">Getting Started Guide</h3>
            <p className="text-lg text-muted-foreground">
              Learn the basics of building AI agents with Plexus in our comprehensive getting started guide.
            </p>
            <Button className="bg-primary text-white" asChild>
              <Link href="/documentation/basics">Read Guide</Link>
            </Button>
          </div>
          <div className="space-y-4">
            <h3 className="text-2xl font-semibold">Best Practices</h3>
            <p className="text-lg text-muted-foreground">
              Discover best practices for developing reliable and scalable AI workflows.
            </p>
            <Button className="bg-primary text-white">Learn More</Button>
          </div>
        </div>
      </StandardSection>

      <CTASection />
      <Footer />
    </Layout>
  )
} 
'use client'

import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Button } from '@/components/ui/button'
import { ArrowRight, BookOpen, GraduationCap, Video, MessageSquare } from 'lucide-react'
import { StandardSection } from '@/components/landing/StandardSection'
import { FrameSection } from '@/components/landing/FrameSection'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'
import { FeatureCard } from '@/components/landing/FeatureCard'

export default function ResourcesPage() {
  return (
    <Layout>
      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
              <div className="flex flex-col xl:flex-row gap-8">
                <div className="flex-1 min-w-0 xl:w-[calc(50%-2rem)]">
                  <h1 className="text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-6 md:mb-12 leading-tight text-center md:text-center xl:text-left">
                    <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">Learn</span> how to build with <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text whitespace-nowrap">AI agents</span>
                  </h1>
                  <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                    <div className="w-full md:w-1/2 xl:w-full flex flex-col items-center md:items-start text-center md:text-left md:justify-center">
                      <p className="text-xl text-muted-foreground mb-8 text-justify w-full">
                        Explore our comprehensive resources to master AI agent development. From getting started guides to advanced tutorials.
                      </p>
                      <p className="text-xl text-muted-foreground mb-8 text-justify w-full">
                        Join our community of developers and AI practitioners to share knowledge and best practices.
                      </p>
                      <div className="flex justify-center xl:justify-start">
                        <Button size="lg" className="bg-primary text-white">
                          Browse Documentation
                          <ArrowRight className="ml-2 h-5 w-5" />
                        </Button>
                      </div>
                    </div>
                    <div className="w-full md:w-1/2 xl:hidden flex justify-center md:justify-end items-center">
                      <div className="w-full max-w-[400px]">
                        <ItemListWorkflow 
                          fixedShapeSequence={["circle", "triangle", "square", "hexagon"]}
                          resultTypes={[
                            { type: "text", values: [{ text: "Learn", color: "true" }] },
                            { type: "text", values: [{ text: "Build", color: "true" }] },
                            { type: "text", values: [{ text: "Deploy", color: "true" }] },
                            { type: "text", values: [{ text: "Scale", color: "true" }] }
                          ]}
                        />
                      </div>
                    </div>
                  </div>
                </div>
                <div className="hidden xl:flex flex-1 min-w-0 xl:w-[calc(50%-2rem)] justify-center md:justify-end items-center">
                  <div className="w-full max-w-[400px]">
                    <ItemListWorkflow 
                      fixedShapeSequence={["circle", "triangle", "square", "hexagon"]}
                      resultTypes={[
                        { type: "text", values: [{ text: "Learn", color: "true" }] },
                        { type: "text", values: [{ text: "Build", color: "true" }] },
                        { type: "text", values: [{ text: "Deploy", color: "true" }] },
                        { type: "text", values: [{ text: "Scale", color: "true" }] }
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

      <FrameSection
        headline="Latest Resources"
        layout="twoColumn"
        leftContent={
          <div className="space-y-6">
            <div className="space-y-4">
              <h3 className="text-2xl font-semibold">Getting Started Guide</h3>
              <p className="text-lg text-muted-foreground">
                Learn the basics of building AI agents with Plexus in our comprehensive getting started guide.
              </p>
              <Button variant="outline">Read Guide</Button>
            </div>
            <div className="space-y-4">
              <h3 className="text-2xl font-semibold">Best Practices</h3>
              <p className="text-lg text-muted-foreground">
                Discover best practices for developing reliable and scalable AI workflows.
              </p>
              <Button variant="outline">Learn More</Button>
            </div>
          </div>
        }
        rightContent={
          <div className="w-full max-w-[400px]">
            <ItemListWorkflow 
              fixedShapeSequence={["square", "circle", "triangle", "hexagon"]}
              resultTypes={[
                { type: "text", values: [{ text: "Guide", color: "true" }] },
                { type: "text", values: [{ text: "Tutorial", color: "true" }] },
                { type: "text", values: [{ text: "Example", color: "true" }] },
                { type: "text", values: [{ text: "Template", color: "true" }] }
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
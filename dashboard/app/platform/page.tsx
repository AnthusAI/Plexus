"use client"

import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { LabelingStrategies } from '@/components/landing/LabelingStrategies'
import { PlatformFeatures } from '@/components/landing/PlatformFeatures'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Hero } from '@/components/landing/Hero'
import { TaskCycleDemo } from '@/components/landing/TaskCycleDemo'
import { StandardSection } from '@/components/landing/StandardSection'
import MetricsGauges from '@/components/MetricsGauges'
import ItemListWorkflow from '@/components/workflow/layouts/item-list-workflow'

const CLOCKWISE_SEQUENCE = [0, 1, 3, 2] // accuracy -> precision -> specificity -> sensitivity

export default function PlatformPage() {
  const [rotationIndex, setRotationIndex] = React.useState(0)

  React.useEffect(() => {
    const interval = setInterval(() => {
      setRotationIndex(prev => (prev + 1) % CLOCKWISE_SEQUENCE.length)
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  // Map rotation index to actual gauge index for clockwise movement
  const selectedIndex = CLOCKWISE_SEQUENCE[rotationIndex]

  return (
    <Layout>
      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
              <div className="flex flex-col xl:flex-row gap-8">
                <div className="flex-1 min-w-0 xl:w-[calc(50%-2rem)]">
                  <h1 className="text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-6 md:mb-12 leading-tight text-center md:text-center xl:text-left">
                    A <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">platform</span> for running <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text whitespace-nowrap">AI agents</span> at <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">industrial scale</span>
                  </h1>
                  <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                    <div className="w-full md:w-1/2 xl:w-full flex flex-col items-center md:items-start text-center md:text-left md:justify-center">
                      <p className="text-xl text-muted-foreground mb-8 text-justify w-full">
                        Plexus is a serverless platform where your team can develop, test, and deploy AI agents without writing any code, and without worrying about the underlying infrastructure.
                      </p>
                      <p className="text-xl text-muted-foreground mb-8 text-justify w-full">
                        Your team knows your business.  Our team knows how to operate AI reliably at scale.  Together, we can build and deploy solutions that transform your business.
                      </p>
                    </div>
                    <div className="w-full md:w-1/2 xl:hidden flex justify-center md:justify-end items-center">
                      <div className="w-full max-w-[400px]">
                        <ItemListWorkflow 
                          fixedShapeSequence={["square", "circle", "triangle", "hexagon"]}
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
                      fixedShapeSequence={["square", "circle", "triangle", "hexagon"]}
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
        headline="Don't Just Guess — Guess and Test"
        headlinePosition="top"
        leftContent={
          <MetricsGauges
            variant="detail"
            selectedIndex={selectedIndex}
            gauges={[
              {
                value: 92,
                label: 'Accuracy',
                segments: [
                  { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                  { start: 60, end: 85, color: 'var(--gauge-converging)' },
                  { start: 85, end: 100, color: 'var(--gauge-great)' }
                ],
                backgroundColor: 'var(--gauge-background)',
              },
              {
                value: 91,
                label: 'Precision',
                segments: [
                  { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                  { start: 60, end: 85, color: 'var(--gauge-converging)' },
                  { start: 85, end: 100, color: 'var(--gauge-great)' }
                ],
                backgroundColor: 'var(--gauge-background)',
              },
              {
                value: 95,
                label: 'Specificity',
                segments: [
                  { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                  { start: 60, end: 85, color: 'var(--gauge-converging)' },
                  { start: 85, end: 100, color: 'var(--gauge-great)' }
                ],
                backgroundColor: 'var(--gauge-background)',
              },
              {
                value: 89,
                label: 'Sensitivity',
                segments: [
                  { start: 0, end: 60, color: 'var(--gauge-inviable)' },
                  { start: 60, end: 85, color: 'var(--gauge-converging)' },
                  { start: 85, end: 100, color: 'var(--gauge-great)' }
                ],
                backgroundColor: 'var(--gauge-background)',
              },
            ]}
          />
        }
        rightContent={
          <div>
            <p className="text-xl text-muted-foreground text-justify">
              You can't just write prompts and put them into production and hope they work, you need a way to evaluate them quantitatively to see if they meet your needs. You can't optimize a metric you're not measuring.
            </p>
            <p className="text-xl text-muted-foreground text-justify mt-4">
              Each use case demands its own success metrics: Is this a regulatory compliance question where we need high sensitivity? Do we need to use balanced accuracy because the data is unbalanced? Plexus gives you the gauges you need.
            </p>
          </div>
        }
      />

      <TaskCycleDemo />
      <PlatformFeatures />
      <LabelingStrategies />
      <CTASection />
      <Footer />
    </Layout>
  )
} 
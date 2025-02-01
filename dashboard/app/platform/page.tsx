import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { LabelingStrategies } from '@/components/landing/LabelingStrategies'
import { PlatformFeatures } from '@/components/landing/PlatformFeatures'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Hero } from '@/components/landing/Hero'

export default function PlatformPage() {
  return (
    <Layout>
      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-24 md:py-32 px-4 md:px-8">
              <div className="max-w-4xl mx-auto text-center">
                <h1 className="text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-8 text-foreground">
                  The Plexus Platform
                </h1>
                <p className="text-xl text-muted-foreground">
                  A complete platform for building and deploying AI workflows at scale
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <PlatformFeatures />
      <LabelingStrategies />
      <CTASection />
      <Footer />
    </Layout>
  )
} 
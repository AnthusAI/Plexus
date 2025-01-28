import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { LabelingStrategies } from '@/components/landing/LabelingStrategies'
import { PlatformFeatures } from '@/components/landing/PlatformFeatures'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'

export default function PlatformPage() {
  return (
    <Layout>
      <section className="bg-muted">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="py-4">
            <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
              <div className="max-w-4xl mx-auto text-center">
                <h1 className="text-4xl md:text-5xl font-bold mb-8 text-foreground">
                  The Plexus Platform
                </h1>
                <p className="text-xl text-muted-foreground mb-12">
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
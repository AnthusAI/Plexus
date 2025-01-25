import React from 'react'
import { Hero } from '@/components/landing/Hero'
import { Features } from '@/components/landing/Features'
import { LabelingStrategies } from '@/components/landing/LabelingStrategies'
import { UseCases } from '@/components/landing/UseCases'
import { Overview } from '@/components/landing/Overview'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'
import { Layout } from '@/components/landing/Layout'

export default function LandingPage() {
  return (
    <Layout>
      <Hero />
      <Overview />
      <UseCases />
      <LabelingStrategies />
      <Features />
      <CTASection />
      <Footer />
    </Layout>
  )
} 
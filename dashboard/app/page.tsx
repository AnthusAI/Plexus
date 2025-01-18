import React from 'react'
import { Hero } from '@/components/landing/Hero'
import { Features } from '@/components/landing/Features'
import { CTASection } from '@/components/landing/CTASection'
import { Layout } from '@/components/landing/Layout'

export default function LandingPage() {
  return (
    <Layout>
      <Hero />
      <Features />
      <CTASection />
    </Layout>
  )
} 
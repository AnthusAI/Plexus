import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { CallCenterQA } from '@/components/landing/CallCenterQA'
import { CTASection } from '@/components/landing/CTASection'
import { Footer } from '@/components/landing/Footer'

export default function CallCenterQAPage() {
  return (
    <Layout>
      <CallCenterQA />
      <CTASection />
      <Footer />
    </Layout>
  )
} 
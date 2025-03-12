import React from 'react'
import type { Metadata } from 'next'
import EvaluationClientLayout from './client-layout'

export const metadata: Metadata = {
  title: "Evaluation Results",
  description: "Metrics and score results for the evaluation.",
  openGraph: {
    title: "Evaluation Results",
    description: "Metrics and score results for the evaluation.",
  },
  twitter: {
    title: "Evaluation Results",
    description: "Metrics and score results for the evaluation.",
  }
}

export default function EvaluationLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Wrap the children with the client layout component
  return <EvaluationClientLayout>{children}</EvaluationClientLayout>
} 
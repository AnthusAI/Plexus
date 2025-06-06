import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Evaluation Results",
  description: "Metrics and score results for one score evaluation.",
  openGraph: {
    title: "Evaluation Results",
    description: "Metrics and score results for one score evaluation.",
  },
  twitter: {
    title: "Evaluation Results",
    description: "Metrics and score results for one score evaluation.",
  }
}

export default function LabEvaluationDetailLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
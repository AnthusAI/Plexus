import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Analysis",
  description: "Investigate patterns, outcomes, and root causes across your account data.",
  openGraph: {
    title: "Analysis",
    description: "Investigate patterns, outcomes, and root causes across your account data.",
  },
  twitter: {
    title: "Analysis",
    description: "Investigate patterns, outcomes, and root causes across your account data.",
  }
}

export default function AnalysisLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}

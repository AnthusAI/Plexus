import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Scorecard",
  description: "Configuration and past version information for one scorecard and its scores.",
  openGraph: {
    title: "Scorecard",
    description: "Configuration and past version information for one scorecard and its scores.",
  },
  twitter: {
    title: "Scorecard",
    description: "Configuration and past version information for one scorecard and its scores.",
  }
}

export default function ScorecardDetailLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
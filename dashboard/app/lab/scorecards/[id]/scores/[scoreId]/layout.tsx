import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Score Configuration",
  description: "Current champion and version history for the configuration for one scorecard score.",
  openGraph: {
    title: "Score Configuration",
    description: "Current champion and version history for the configuration for one scorecard score.",
  },
  twitter: {
    title: "Score Configuration",
    description: "Current champion and version history for the configuration for one scorecard score.",
  }
}

export default function ScoreDetailLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
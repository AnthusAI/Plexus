import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Scorecard Scores",
  description: "All scores for this scorecard with their configurations and versions.",
  openGraph: {
    title: "Scorecard Scores",
    description: "All scores for this scorecard with their configurations and versions.",
  },
  twitter: {
    title: "Scorecard Scores",
    description: "All scores for this scorecard with their configurations and versions.",
  }
}

export default function ScoresLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
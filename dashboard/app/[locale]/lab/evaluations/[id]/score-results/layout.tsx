import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Score Results",
  description: "Detailed score results for this evaluation.",
  openGraph: {
    title: "Score Results",
    description: "Detailed score results for this evaluation.",
  },
  twitter: {
    title: "Score Results",
    description: "Detailed score results for this evaluation.",
  }
}

export default function ScoreResultsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
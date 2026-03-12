import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Score Result Detail",
  description: "Detailed view of an individual score result.",
  openGraph: {
    title: "Score Result Detail",
    description: "Detailed view of an individual score result.",
  },
  twitter: {
    title: "Score Result Detail",
    description: "Detailed view of an individual score result.",
  }
}

export default function ScoreResultDetailLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
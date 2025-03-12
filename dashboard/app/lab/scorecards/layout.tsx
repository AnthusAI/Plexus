import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Scorecards",
  description: "The configurations and past versions for all scorecards and scores.",
  openGraph: {
    title: "Scorecards",
    description: "The configurations and past versions for all scorecards and scores.",
  },
  twitter: {
    title: "Scorecards",
    description: "The configurations and past versions for all scorecards and scores.",
  }
}

export default function ScorecardsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
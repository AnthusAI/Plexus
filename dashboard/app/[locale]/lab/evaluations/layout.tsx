import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Evaluations",
  description: "Recent evaluations with metrics and results.",
  openGraph: {
    title: "Evaluations",
    description: "Recent evaluations with metrics and results.",
  },
  twitter: {
    title: "Evaluations",
    description: "Recent evaluations with metrics and results.",
  }
}

export default function EvaluationsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
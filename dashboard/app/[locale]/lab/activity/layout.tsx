import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Recent Activity",
  description: "Tasks of any kind, with information about their configurations and results.",
  openGraph: {
    title: "Recent Activity",
    description: "Tasks of any kind, with information about their configurations and results.",
  },
  twitter: {
    title: "Recent Activity",
    description: "Tasks of any kind, with information about their configurations and results.",
  }
}

export default function ActivityLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Datasets",
  description: "Manage and explore your datasets for AI evaluation.",
  openGraph: {
    title: "Datasets",
    description: "Manage and explore your datasets for AI evaluation.",
  },
  twitter: {
    title: "Datasets",
    description: "Manage and explore your datasets for AI evaluation.",
  }
}

export default function DatasetsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
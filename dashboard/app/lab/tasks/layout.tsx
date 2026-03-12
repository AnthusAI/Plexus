import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Tasks",
  description: "Processing tasks and job status.",
  openGraph: {
    title: "Tasks",
    description: "Processing tasks and job status.",
  },
  twitter: {
    title: "Tasks",
    description: "Processing tasks and job status.",
  }
}

export default function TasksLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
import React from 'react'
import type { Metadata } from 'next'
import ReportClientLayout from './client-layout'

export const metadata: Metadata = {
  title: "Report",
  description: "View report results and analysis.",
  openGraph: {
    title: "Report",
    description: "View report results and analysis.",
  },
  twitter: {
    title: "Report",
    description: "View report results and analysis.",
  }
}

export default function ReportLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <ReportClientLayout>{children}</ReportClientLayout>
} 
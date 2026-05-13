import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Console",
  description: "Chat, board, and activity tools for your account.",
  openGraph: {
    title: "Console",
    description: "Chat, board, and activity tools for your account.",
  },
  twitter: {
    title: "Console",
    description: "Chat, board, and activity tools for your account.",
  }
}

export default function ConsoleLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}

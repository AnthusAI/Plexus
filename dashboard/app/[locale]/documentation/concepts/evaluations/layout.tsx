import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Evaluations - Plexus Documentation",
  description: "Learn about Evaluations in Plexus - how content is assessed using scorecards"
}

export default function EvaluationsLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
} 
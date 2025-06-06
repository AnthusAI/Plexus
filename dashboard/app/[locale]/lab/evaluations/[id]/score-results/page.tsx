'use client'

import { useParams, redirect } from 'next/navigation'

export default function ScoreResults() {
  const { id } = useParams() as { id: string }
  
  // Redirect to the evaluation page if no score result ID is provided
  redirect(`/lab/evaluations/${id}`)
} 
'use client'

import { useParams } from 'next/navigation'
import { redirect } from '@/i18n/navigation'

export default function ScoreResults() {
  const { id } = useParams() as { id: string }
  
  // Redirect to the evaluation page if no score result ID is provided
  redirect(`/lab/evaluations/${id}`)
} 
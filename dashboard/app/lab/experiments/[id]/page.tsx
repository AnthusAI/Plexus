'use client'

import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'

export default function LabExperimentDetail() {
  const { id } = useParams() as { id: string }
  const router = useRouter()
  
  useEffect(() => {
    router.replace(`/lab/procedures/${id}`)
  }, [router, id])
  
  return (
    <div className="flex items-center justify-center h-64">
      <p>Redirecting to Procedures...</p>
    </div>
  )
}
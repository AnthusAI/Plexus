'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function LabExperiments() {
  const router = useRouter()
  
  useEffect(() => {
    router.replace('/lab/procedures')
  }, [router])
  
  return (
    <div className="flex items-center justify-center h-64">
      <p>Redirecting to Procedures...</p>
    </div>
  )
}
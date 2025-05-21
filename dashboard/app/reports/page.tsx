'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function ReportsRedirectPage() {
  const router = useRouter()

  useEffect(() => {
    // Redirect to the lab reports route
    router.push('/lab/reports')
  }, [router])

  return null
} 
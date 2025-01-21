"use client"

import { useAuthenticator } from '@aws-amplify/ui-react'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function DashboardPage() {
  const { authStatus } = useAuthenticator()
  const router = useRouter()
  
  useEffect(() => {
    if (authStatus === 'authenticated') {
      router.push('/activity')
    }
  }, [authStatus, router])

  // Return null while redirecting
  return null
}

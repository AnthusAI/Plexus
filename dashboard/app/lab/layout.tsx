'use client'

import React from 'react'
import DashboardLayout from '@/components/dashboard-layout'
import { signOut as amplifySignOut } from 'aws-amplify/auth'
import { useRouter } from 'next/navigation'

export default function LabLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()

  const handleSignOut = async () => {
    try {
      await amplifySignOut()
      router.push('/')
    } catch (error) {
      console.error('Error signing out:', error)
    }
  }

  return (
    <DashboardLayout signOut={handleSignOut}>
      {children}
    </DashboardLayout>
  )
} 
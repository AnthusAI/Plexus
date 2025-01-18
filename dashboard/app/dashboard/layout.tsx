"use client"

import { ReactNode } from 'react'
import { Authenticator } from '@aws-amplify/ui-react'
import SquareLogo, { LogoVariant } from '@/components/logo-square'

interface DashboardLayoutProps {
  children: ReactNode
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="min-h-screen bg-background">
      <div className="flex flex-col md:flex-row items-center justify-center min-h-screen gap-8 p-4">
        <div className="w-full max-w-[300px]">
          <SquareLogo variant={LogoVariant.Square} className="w-full" />
        </div>
        <div className="w-full max-w-md">
          <Authenticator hideSignUp={true}>
            {children}
          </Authenticator>
        </div>
      </div>
    </div>
  )
} 
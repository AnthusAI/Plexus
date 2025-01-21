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
        <div className="w-full max-w-[300px] relative">
          <div className="absolute inset-[-2rem] bg-gradient-to-r from-secondary to-primary rounded-[2rem] blur-2xl opacity-30"></div>
          <div className="relative">
            <SquareLogo variant={LogoVariant.Square} className="w-full" />
          </div>
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
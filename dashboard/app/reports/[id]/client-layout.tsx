'use client'

import React from 'react'
import { useParams } from 'next/navigation'
import SquareLogo, { LogoVariant } from '@/components/logo-square'
import { ReportService } from './page'

export default function ReportClientLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { id } = useParams() as { id: string }
  const isShareToken = new ReportService().isValidToken(id)
  
  // Use the custom share layout for all report views
  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* Main content - fills available space and handles overflow */}
      <main className="flex-1 overflow-hidden">
        {children}
      </main>
      
      {/* Custom minimal footer - stays at the bottom */}
      <footer className="py-4 px-6 flex-shrink-0">
        <div className="flex items-center justify-end">
          <span className="text-sm text-muted-foreground mr-2">powered by</span>
          <a 
            href="https://plexus.anth.us" 
            target="_blank" 
            rel="noopener noreferrer"
            className="relative w-24 h-8"
          >
            <SquareLogo variant={LogoVariant.Wide} />
          </a>
        </div>
      </footer>
    </div>
  )
} 
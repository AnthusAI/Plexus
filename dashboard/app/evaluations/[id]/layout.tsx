'use client'

import React from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import SquareLogo, { LogoVariant } from '@/components/logo-square'
import { EvaluationService } from './page'

export default function EvaluationLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { id } = useParams() as { id: string }
  const isShareToken = new EvaluationService().isValidToken(id)

  // If this is a share token, use the custom share layout
  if (isShareToken) {
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
  
  // For non-share URLs, just return the children
  return children
} 
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
      <div className="min-h-screen bg-background">
        {/* Main content - fills exactly the viewport height */}
        <main className="h-screen w-full">
          {children}
        </main>
        
        {/* Custom minimal footer - appears below the viewport */}
        <footer className="py-4 px-6">
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
"use client"

import React from 'react'
import { Button } from "@/components/ui/button"
import { ArrowRight, AlertCircle, Loader2 } from 'lucide-react'
import { useState } from 'react'

export const CTASection = () => {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleEarlyAccess = async () => {
    setIsLoading(true)
    setError(null)
    try {
      await new Promise(resolve => setTimeout(resolve, 100))
      const newWindow = window.open('https://docs.google.com/forms/d/e/1FAIpQLSdWlt4KpwPSBHzg3o8fikHcfrzxo5rCcV-0-zDt815NZ1tcyg/viewform?usp=sf_link', '_blank')
      if (!newWindow) {
        throw new Error('Popup blocked')
      }
    } catch (err) {
      setError('Failed to open form. Please disable popup blocker and try again.')
      console.error('Navigation error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <section className="py-20 bg-gradient-to-b from-background to-muted">
      <div className="container mx-auto px-4 text-center">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Ready to get started with Plexus?
          </h2>
          <p className="text-xl text-muted-foreground mb-8">
            Join the growing community of businesses building powerful AI workflows with Plexus.
          </p>
          <Button 
            size="lg" 
            className="bg-gradient-to-r from-secondary to-primary text-white hover:from-secondary/90 hover:to-primary/90 text-lg font-semibold"
            onClick={handleEarlyAccess}
            disabled={isLoading}
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" role="img" aria-label="loading" />
            ) : (
              <>
                Request Early Access
                <ArrowRight className="ml-2 h-5 w-5" />
              </>
            )}
          </Button>
          {error && (
            <div className="mt-4 flex items-center justify-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}


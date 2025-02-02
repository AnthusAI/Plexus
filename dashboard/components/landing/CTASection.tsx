"use client"

import React from 'react'
import { Button } from "@/components/ui/button"
import { ArrowRight, AlertCircle, Loader2 } from 'lucide-react'
import { useState } from 'react'
import SquareLogo, { LogoVariant } from '@/components/logo-square'

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
    <section className="relative -mt-16 pt-8 pb-8 px-4 md:px-8 bg-card">
      <div className="absolute top-0 left-0 w-full h-96 pointer-events-none bg-gradient-to-b from-background to-card"></div>
      <div className="relative z-10 w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className="py-4">
          <div className="py-8 md:py-8 px-4 md:px-8">
            <div className="flex flex-col md:flex-row items-center gap-12">
              <div className="flex-1 text-center md:text-left">
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Ready to get started?
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
                  <div className="mt-4 flex items-center justify-center md:justify-start gap-2 text-destructive">
                    <AlertCircle className="h-5 w-5" />
                    <span>{error}</span>
                  </div>
                )}
              </div>
              <div className="w-48 h-48 md:w-64 md:h-64 flex-shrink-0 relative">
                <div
                  className="absolute inset-[-2rem] bg-gradient-to-r from-secondary to-primary rounded-[2rem] blur-2xl opacity-30"
                  style={{ transform: "translateZ(0)", willChange: "opacity, transform" }}
                ></div>
                <div className="relative z-10">
                  <SquareLogo variant={LogoVariant.Square} className="w-full h-full" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}


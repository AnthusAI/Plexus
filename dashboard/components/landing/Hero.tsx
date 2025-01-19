"use client"

import React from 'react'
import { Button } from "@/components/ui/button"
import { ArrowRight, Loader2, AlertCircle } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import SquareLogo, { LogoVariant } from '@/components/logo-square'

interface HeroProps {
  mockRouter?: {
    push: (url: string) => Promise<void>
  }
}

export const Hero = ({ mockRouter }: HeroProps = {}) => {
  const realRouter = useRouter()
  const router = mockRouter || realRouter
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleLogin = async (e: React.MouseEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)
    try {
      await router.push('/dashboard')
    } catch (err) {
      setError('Failed to navigate to dashboard. Please try again.')
      console.error('Navigation error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <section className="container mx-auto px-4 py-20 md:py-32">
      <div className="flex flex-col md:flex-row items-center gap-8">
        <div className="w-full md:w-1/2 flex flex-col items-center md:items-start text-center md:text-left">
          <h1 className="text-5xl md:text-7xl font-bold tracking-tighter mb-6 max-w-4xl leading-tight">
            Run{' '}
            <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">
              AI agents
            </span>{' '}
            over{' '}
            <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text">
              your data
            </span>{' '}
            with{' '}
            <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text">
              no code
            </span>
          </h1>
          <p className="text-xl md:text-2xl text-muted-foreground mb-8 max-w-3xl">
            Plexus is a battle-tested task-dispatching platform for building agent-based AI workflows that analyze streams of content and take action.
          </p>
          <div className="flex flex-col sm:flex-row gap-4">
            <Button size="lg" className="w-full sm:w-auto bg-primary text-white hover:bg-primary/90 text-lg font-semibold">
              Learn More
            </Button>
            <Button 
              size="lg" 
              className="w-full sm:w-auto bg-secondary text-white hover:bg-secondary/90 text-lg font-semibold"
              onClick={handleLogin}
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-5 w-5 animate-spin" role="img" aria-label="loading" />
              ) : (
                <>
                  Log In
                  <ArrowRight className="ml-2 h-5 w-5" />
                </>
              )}
            </Button>
          </div>
          {error && (
            <div className="mt-4 flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>{error}</span>
            </div>
          )}
        </div>
        <div className="w-full md:w-1/2 relative p-4">
          <div className="absolute inset-[-2rem] bg-gradient-to-r from-secondary to-primary rounded-[2rem] blur-2xl opacity-30"></div>
          <div className="relative z-10">
            <SquareLogo 
              variant={LogoVariant.Square} 
              className="w-full"
            />
          </div>
        </div>
      </div>
    </section>
  )
}


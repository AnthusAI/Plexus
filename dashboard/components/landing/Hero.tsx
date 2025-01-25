"use client"

import React from 'react'
import { Button } from "@/components/ui/button"
import { ArrowRight } from 'lucide-react'
import SquareLogo, { LogoVariant } from '@/components/logo-square'

export const Hero = () => {
  return (
    <section className="container mx-auto px-4 py-20 md:py-32">
      <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center gap-8">
        <div className="w-full md:w-2/3 flex flex-col items-center md:items-start text-center md:text-left">
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
            Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.
          </p>
          <div className="flex flex-col sm:flex-row gap-4">
            <Button size="lg" className="w-full sm:w-auto bg-primary text-white hover:bg-primary/90 text-lg font-semibold">
              Learn More
            </Button>
          </div>
        </div>
        <div className="w-full md:w-1/3 relative p-4">
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


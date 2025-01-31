"use client"

import React from 'react'
import { Button } from "@/components/ui/button"
import { ArrowRight } from 'lucide-react'
import WorkflowIllustration from './workflow'

export function Hero() {
  return (
    <section className="bg-muted">
      <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className="py-4">
          <div className="bg-background rounded-xl py-12 md:py-16 px-4 md:px-8">
            <div className="flex flex-col xl:flex-row gap-8">
              <div className="flex-1 min-w-0">
                <h1 className="text-5xl lg:text-6xl xl:text-7xl font-bold tracking-tighter mb-6 md:mb-12 leading-tight text-center md:text-center xl:text-left">
                  Run <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">AI agents</span> over <span className="text-transparent bg-gradient-to-r from-secondary to-accent bg-clip-text whitespace-nowrap">your data</span> with <span className="text-transparent bg-gradient-to-r from-primary to-accent bg-clip-text whitespace-nowrap">no code</span>
                </h1>
                <div className="flex flex-col md:flex-row xl:flex-col gap-8">
                  <div className="w-full md:w-1/2 xl:w-full flex flex-col items-center md:items-start text-center md:text-left md:justify-center">
                    <p className="text-xl md:text-2xl text-muted-foreground mb-8 text-justify w-full">
                      Plexus is a battle-tested platform for building AI workflows that analyze streams of content and take action.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-4">
                      <Button size="lg" className="w-full sm:w-auto bg-primary text-white hover:bg-primary/90 text-lg font-semibold">
                        Learn More
                      </Button>
                    </div>
                  </div>
                  <div className="w-full md:w-1/2 xl:hidden flex justify-center md:justify-end items-center">
                    <div className="w-full max-w-[400px]">
                      <WorkflowIllustration />
                    </div>
                  </div>
                </div>
              </div>
              <div className="hidden xl:flex flex-1 min-w-0 justify-center md:justify-end items-center">
                <div className="w-full max-w-[400px]">
                  <WorkflowIllustration />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}


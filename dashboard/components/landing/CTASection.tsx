"use client"

import { Button } from "@/components/ui/button"
import { ArrowRight } from 'lucide-react'

export const CTASection = () => {
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
            onClick={() => window.open('https://docs.google.com/forms/d/e/1FAIpQLSdWlt4KpwPSBHzg3o8fikHcfrzxo5rCcV-0-zDt815NZ1tcyg/viewform?usp=sf_link', '_blank')}
          >
            Request Early Access
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </div>
    </section>
  )
}


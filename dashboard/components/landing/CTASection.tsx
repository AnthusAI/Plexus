"use client"

import React from 'react'
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ArrowRight } from 'lucide-react'
import BrandableLogo from '@/components/BrandableLogo'
import { LogoVariant } from '@/components/logo-square'

/** The Anth.us contact page, with the solution and the place on this site the visitor came from named. */
export const EARLY_ACCESS_URL = 'https://anth.us/engage/?solution=Primus&cta=early-access'

export const CTASection = () => {
  return (
    <section className="relative pt-24 pb-8 px-4 md:px-8 bg-card">
      <div className="absolute inset-x-0 top-0 h-48 bg-gradient-to-b from-background to-card"></div>
      <div className="relative z-10 w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className="py-4">
          <div className="py-8 md:py-8 px-4 md:px-8">
            <div className="flex flex-col md:flex-row items-center gap-12">
              <div className="flex-1 text-center md:text-left">
                <Badge variant="outline" className="mb-4">Early access</Badge>
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Ready to get started?
                </h2>
                <p className="text-xl text-muted-foreground mb-8">
                  Join the growing community of businesses building powerful AI workflows with Primus.
                </p>
                <Button
                  size="lg"
                  className="bg-gradient-to-r from-secondary to-primary text-white hover:from-secondary/90 hover:to-primary/90 text-lg font-semibold"
                  asChild
                >
                  <a href={EARLY_ACCESS_URL} data-cta-location="band">
                    Request Early Access
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </a>
                </Button>
              </div>
              <div className="w-48 h-48 md:w-64 md:h-64 flex-shrink-0 relative">
                <div
                  className="absolute inset-[-2rem] bg-gradient-to-r from-secondary to-primary rounded-[2rem] blur-2xl opacity-30"
                  style={{ transform: "translateZ(0)", willChange: "opacity, transform" }}
                ></div>
                <div className="relative z-10">
                  <BrandableLogo variant={LogoVariant.Square} className="w-full h-full" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}


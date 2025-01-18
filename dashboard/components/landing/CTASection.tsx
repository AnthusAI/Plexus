import { Button } from "@/components/ui/button"
import { ArrowRight } from 'lucide-react'

export const CTASection = () => {
  return (
    <section className="py-20 bg-gradient-to-b from-white to-gray-50">
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
            className="bg-gradient-to-r from-fuchsia-500 to-blue-500 hover:from-fuchsia-600 hover:to-blue-600"
            onClick={() => window.open('https://docs.google.com/forms/d/e/1FAIpQLSdWlt4KpwPSBHzg3o8fikHcfrzxo5rCcV-0-zDt815NZ1tcyg/viewform?usp=sf_link', '_blank')}
          >
            Request Early Access
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    </section>
  )
}


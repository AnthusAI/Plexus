import React from 'react'
import Link from 'next/link'
import { Github, Linkedin, MessageCircle, Mail } from 'lucide-react'

export const Footer = () => {
  return (
    <footer className="bg-muted py-12">
      <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
        <div className="py-4">
          <div className="py-12 md:py-16 px-4 md:px-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div>
                <h3 className="text-lg font-semibold mb-4">About</h3>
                <p className="text-muted-foreground mb-4">
                  Plexus is a product of Anthus AI Solutions. We deliver serverless business 
                  solutions using collaboration between human and artificial 
                  intelligence.
                </p>
                <Link 
                  href="https://anth.us" 
                  className="text-accent hover:text-accent/90"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Learn more about Anthus AI Solutions →
                </Link>
              </div>
              
              <div>
                <h3 className="text-lg font-semibold mb-4">Resources</h3>
                <ul className="space-y-2">
                  <li>
                    <Link 
                      href="/documentation"
                      className="text-muted-foreground hover:text-foreground"
                    >
                      Documentation
                    </Link>
                  </li>
                  <li>
                    <Link 
                      href="https://anthusai.github.io/Plexus/"
                      className="text-muted-foreground hover:text-foreground"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Python SDK
                    </Link>
                  </li>
                  <li>
                    <Link 
                      href="https://github.com/AnthusAI/Plexus/blob/main/CHANGELOG.md"
                      className="text-muted-foreground hover:text-foreground"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Change Log
                    </Link>
                  </li>
                  <li>
                    <Link 
                      href="https://anth.us/blog" 
                      className="text-muted-foreground hover:text-foreground"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Articles
                    </Link>
                  </li>
                </ul>
              </div>
              
              <div>
                <h3 className="text-lg font-semibold mb-4">Connect</h3>
                <div className="flex space-x-4">
                  <Link
                    href="https://github.com/AnthusAI"
                    className="text-muted-foreground hover:text-foreground"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Follow us on GitHub"
                  >
                    <Github className="h-6 w-6" />
                  </Link>
                  <Link
                    href="https://www.linkedin.com/company/anthus-ai-solutions"
                    className="text-muted-foreground hover:text-foreground"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Connect on LinkedIn"
                  >
                    <Linkedin className="h-6 w-6" />
                  </Link>
                  <Link
                    href="https://discord.gg/uStyWraJ2M"
                    className="text-muted-foreground hover:text-foreground"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Join us on Discord"
                  >
                    <MessageCircle className="h-6 w-6" />
                  </Link>
                  <Link
                    href="https://docs.google.com/forms/d/e/1FAIpQLSdWlt4KpwPSBHzg3o8fikHcfrzxo5rCcV-0-zDt815NZ1tcyg/viewform?usp=sf_link"
                    className="text-muted-foreground hover:text-foreground"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Contact Us"
                  >
                    <Mail className="h-6 w-6" />
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
} 
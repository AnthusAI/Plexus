'use client'

import React, { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Menu, ArrowRight, Loader2, AlertCircle } from 'lucide-react'
import SquareLogo, { LogoVariant } from '../logo-square'
import { Button } from '../ui/button'
import { cn } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu'

const landingPages = [
  { href: '/solutions/platform', label: 'Platform' },
  { href: '/solutions/optimizer-agents', label: 'Optimizer Agents' },
  { href: '/solutions/enterprise', label: 'Enterprise' },
  { href: '/solutions/resources', label: 'Resources' }
]

export function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const [visiblePages, setVisiblePages] = useState(landingPages.slice(0, 1))
  const [overflowPages, setOverflowPages] = useState(landingPages.slice(1))
  const containerRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [isLoading, setIsLoading] = useState(false)
  
  useEffect(() => {
    const updateVisibleItems = () => {
      if (!containerRef.current || !menuRef.current) return
      
      const containerWidth = containerRef.current.offsetWidth
      const menuWidth = menuRef.current.offsetWidth
      const availableWidth = containerWidth - menuWidth - 48 // 48px for padding and spacing
      
      // Calculate how many items can fit
      const itemWidth = 100 // Approximate width of each item including gap
      const possibleItems = Math.max(1, Math.floor(availableWidth / itemWidth))
      
      if (possibleItems >= landingPages.length) {
        setVisiblePages(landingPages)
        setOverflowPages([])
      } else {
        setVisiblePages(landingPages.slice(0, possibleItems))
        setOverflowPages(landingPages.slice(possibleItems))
      }
    }

    updateVisibleItems()
    window.addEventListener('resize', updateVisibleItems)
    return () => window.removeEventListener('resize', updateVisibleItems)
  }, [])

  const handleSignIn = async (e: React.MouseEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      await router.push('/dashboard')
    } catch (err) {
      console.error('Navigation error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background overflow-x-hidden">
      <nav className="bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto">
          <div className="flex h-14 items-center px-4 md:px-8" ref={containerRef}>
            <div className="flex items-center flex-1">
              <Link href="/" className="mr-4 flex items-center">
                <div className="relative">
                  <div className="absolute -inset-2 bg-gradient-to-r from-secondary to-primary rounded-md blur-sm opacity-15"></div>
                  <div className="relative w-24 h-8">
                    <SquareLogo variant={LogoVariant.Wide} />
                  </div>
                </div>
              </Link>
              <div className="flex gap-4">
                {visiblePages.map((page) => (
                  <Link
                    key={page.href}
                    href={page.href}
                    className={cn(
                      "text-sm font-medium transition-colors hover:text-foreground/80 whitespace-nowrap relative",
                      pathname === page.href ? "text-foreground after:absolute after:left-0 after:right-0 after:-bottom-1 after:h-[2px] after:bg-foreground" : "text-foreground/60"
                    )}
                  >
                    {page.label}
                  </Link>
                ))}
              </div>
            </div>
            <div ref={menuRef} className="flex items-center gap-4">
              {overflowPages.length > 0 && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button 
                      variant="ghost" 
                      size="sm"
                      className="h-8 w-8 p-0"
                    >
                      <Menu className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {overflowPages.map((page) => (
                      <DropdownMenuItem key={page.href} asChild>
                        <Link
                          href={page.href}
                          className={`whitespace-nowrap ${pathname === page.href ? 'text-foreground' : 'text-foreground/60'}`}
                        >
                          {page.label}
                        </Link>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
              <Button 
                size="sm"
                className="bg-secondary text-white hover:bg-secondary/90"
                onClick={handleSignIn}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  'Sign In'
                )}
              </Button>
            </div>
          </div>
        </div>
      </nav>
      <main>{children}</main>
    </div>
  )
}


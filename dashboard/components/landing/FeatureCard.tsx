import React from 'react'
import Link from 'next/link'
import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface FeatureCardProps {
  title: string
  description: string
  icon: LucideIcon
  href?: string
  className?: string
}

export function FeatureCard({
  title,
  description,
  icon: Icon,
  href,
  className
}: FeatureCardProps) {
  const content = (
    <div className={cn(
      "bg-card p-6 rounded-lg shadow-md transition-all duration-300 hover:shadow-xl",
      className
    )}>
      <Icon className="float-right ml-4 w-12 h-12 text-accent" />
      <h3 className={cn(
        "text-xl font-semibold mb-2 text-foreground",
        href && "hover:text-accent"
      )}>
        {title}
      </h3>
      <p className="text-muted-foreground">
        {description}
      </p>
    </div>
  )

  if (href) {
    return (
      <Link href={href}>
        {content}
      </Link>
    )
  }

  return content
} 
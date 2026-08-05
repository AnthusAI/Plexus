"use client"

import React, { type ReactNode } from "react"

import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

/** Shared, flat-shaded empty/loading/error presentation for sidebar feeds. */
export function FeedPresentation({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex h-full items-center justify-center px-5 text-center", className)}>
      {children}
    </div>
  )
}

export function FeedLoading({ className }: { className?: string }) {
  return (
    <FeedPresentation className={className}>
      <Spinner size="lg" />
    </FeedPresentation>
  )
}

export function FeedEmpty({
  title,
  description,
  className,
}: {
  title: string
  description?: string
  className?: string
}) {
  return (
    <FeedPresentation className={className}>
      <div>
        <p className="text-sm text-muted-foreground">{title}</p>
        {description ? <p className="mt-2 text-xs text-muted-foreground">{description}</p> : null}
      </div>
    </FeedPresentation>
  )
}

export function FeedError({
  title,
  detail,
  className,
}: {
  title: string
  detail?: string | null
  className?: string
}) {
  return (
    <FeedPresentation className={className}>
      <div>
        <p className="mb-2 text-sm text-destructive">{title}</p>
        {detail ? <p className="text-xs text-muted-foreground">{detail}</p> : null}
      </div>
    </FeedPresentation>
  )
}

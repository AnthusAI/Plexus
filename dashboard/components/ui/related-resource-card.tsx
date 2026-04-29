"use client"

import * as React from "react"
import NextLink from "next/link"
import { ChevronDown, ChevronRight, Link as LinkIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"

export interface RelatedResourceCardProps {
  label: string
  summary: React.ReactNode
  href?: string | null
  children: React.ReactNode
  className?: string
  linkLabel?: string
}

export function RelatedResourceCard({
  label,
  summary,
  href,
  children,
  className,
  linkLabel = "Open related resource",
}: RelatedResourceCardProps) {
  const [isOpen, setIsOpen] = React.useState(false)

  React.useEffect(() => {
    setIsOpen(false)
  }, [href, label])

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className={cn("bg-background rounded-md", className)}>
        <div className="flex min-w-0 items-center gap-1 pr-2">
          <CollapsibleTrigger asChild>
            <button type="button" className="min-w-0 flex-1 py-2 text-left">
              <div className="flex min-w-0 items-center gap-2">
                {isOpen ? (
                  <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <div className="flex min-w-0 items-center gap-1.5 text-xs truncate">
                  <span className="font-medium truncate">{label}</span>
                  <span className="text-muted-foreground">·</span>
                  <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground truncate">
                    {summary}
                  </span>
                </div>
              </div>
            </button>
          </CollapsibleTrigger>
          {href && (
            <NextLink
              href={href}
              aria-label={linkLabel}
              title={linkLabel}
              className="shrink-0 rounded-sm p-1 text-foreground hover:bg-card"
            >
              <LinkIcon className="h-4 w-4" />
            </NextLink>
          )}
        </div>
        <CollapsibleContent>
          <div className="pb-2 text-sm text-muted-foreground">
            {children}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  )
}

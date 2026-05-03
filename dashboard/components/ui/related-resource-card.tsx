"use client"

import * as React from "react"
import NextLink from "next/link"
import { ChevronDown, ChevronRight, Link as LinkIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Timestamp } from "@/components/ui/timestamp"

export interface RelatedResourceCardProps {
  label: string
  summary: React.ReactNode
  href?: string | null
  children: React.ReactNode
  className?: string
  linkLabel?: string
  collapsible?: boolean
  rowDensity?: "default" | "dense"
  rightMeta?: React.ReactNode
  rightTimestamp?: string | Date | null
  inlineLink?: boolean
}

export function RelatedResourceCard({
  label,
  summary,
  href,
  children,
  className,
  linkLabel = "Open related resource",
  collapsible = true,
  rowDensity = "default",
  rightMeta,
  rightTimestamp,
  inlineLink = false,
}: RelatedResourceCardProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  const hasContent = children !== null && children !== undefined && children !== false && children !== ""
  const nonCollapsibleHeaderPadding = rowDensity === "dense" ? "py-0.5" : "py-1.5"
  const linkPadding = rowDensity === "dense" ? "p-0.5" : "p-1"

  React.useEffect(() => {
    if (!collapsible) {
      setIsOpen(true)
      return
    }
    setIsOpen(false)
  }, [href, label, collapsible])

  const header = (
    <div className="flex min-w-0 items-center gap-0.5 pr-2">
      <div className="min-w-0 flex-1">
        {collapsible ? (
          <CollapsibleTrigger asChild>
            <button type="button" className="min-w-0 py-2 text-left">
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
        ) : (
          <div className={cn("min-w-0 text-left", nonCollapsibleHeaderPadding)}>
            <div className="flex min-w-0 items-center gap-2">
              <div className="flex min-w-0 items-center gap-1.5 text-xs truncate">
                <span className="font-medium truncate">{label}</span>
                <span className="text-muted-foreground">:</span>
                <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground truncate">
                  {summary}
                </span>
                {inlineLink && href && (
                  <NextLink
                    href={href}
                    aria-label={linkLabel}
                    title={linkLabel}
                    className={cn("shrink-0 rounded-sm text-foreground hover:bg-card", linkPadding)}
                    onClick={(event) => event.stopPropagation()}
                  >
                    <LinkIcon className="h-4 w-4" />
                  </NextLink>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
      {((href && !inlineLink) || rightMeta || rightTimestamp) && (
        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          {href && !inlineLink && (
            <NextLink
              href={href}
              aria-label={linkLabel}
              title={linkLabel}
              className={cn("shrink-0 rounded-sm text-foreground hover:bg-card", linkPadding)}
              onClick={(event) => event.stopPropagation()}
            >
              <LinkIcon className="h-4 w-4" />
            </NextLink>
          )}
          {rightTimestamp && (
            <Timestamp time={rightTimestamp} variant="relative" />
          )}
          {rightMeta}
        </div>
      )}
    </div>
  )

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen} disabled={!collapsible}>
      <div className={cn("bg-background rounded-md", className)}>
        {header}
        {collapsible && hasContent ? (
          <CollapsibleContent>
            <div className="pb-2 text-sm text-muted-foreground">
              {children}
            </div>
          </CollapsibleContent>
        ) : hasContent ? (
          <div className="pb-1.5 text-sm text-muted-foreground">
            {children}
          </div>
        ) : null}
      </div>
    </Collapsible>
  )
}

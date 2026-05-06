"use client"

import * as React from "react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  type AttributedUserProfile,
  useAttributedUserProfiles,
} from "@/components/ui/chat-message-user-avatar"
import { cn } from "@/lib/utils"
import { ensureCurrentUserProfile } from "@/utils/user-profile"

function initialsFromProfile(profile: AttributedUserProfile): string {
  if (profile.initials?.trim()) return profile.initials.trim().slice(0, 2).toUpperCase()
  const source = profile.displayName || profile.email || "U"
  return source.slice(0, 2).toUpperCase()
}

export function TaskAuthorIndicator({
  createdByUserId,
  className,
}: {
  createdByUserId?: string | null
  className?: string
}) {
  const normalizedUserId = typeof createdByUserId === "string" ? createdByUserId.trim() : ""
  const usersById = useAttributedUserProfiles([normalizedUserId || undefined])
  const [currentUserProfile, setCurrentUserProfile] = React.useState<AttributedUserProfile | null>(null)

  React.useEffect(() => {
    let cancelled = false
    if (!normalizedUserId) {
      setCurrentUserProfile(null)
      return
    }
    setCurrentUserProfile(null)

    ensureCurrentUserProfile()
      .then((profile) => {
        if (cancelled || !profile || profile.id !== normalizedUserId) {
          return
        }
        setCurrentUserProfile({
          id: profile.id,
          email: profile.email,
          displayName: profile.displayName,
          initials: profile.initials,
          gravatarUrl: profile.gravatarUrl ?? "",
        })
      })
      .catch(() => {
        if (!cancelled) {
          setCurrentUserProfile(null)
        }
      })

    return () => {
      cancelled = true
    }
  }, [normalizedUserId])

  const profile = normalizedUserId ? usersById[normalizedUserId] ?? currentUserProfile ?? undefined : undefined
  const [open, setOpen] = React.useState(false)

  if (!normalizedUserId || !profile) {
    return null
  }

  const initials = initialsFromProfile(profile)

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      data-testid="task-author-indicator"
    >
      <Avatar
        aria-label={`Task author: ${profile.email}`}
        className="h-7 w-7 bg-muted"
      >
        <AvatarImage
          src={profile.gravatarUrl}
          alt={`${profile.displayName} avatar`}
          referrerPolicy="no-referrer"
        />
        <AvatarFallback className="bg-muted text-[10px] font-medium uppercase text-muted-foreground">
          {initials}
        </AvatarFallback>
      </Avatar>
      {open && (
        <div className="pointer-events-none absolute right-0 top-full z-50 mt-2.5 whitespace-nowrap text-right text-xs leading-tight text-muted-foreground">
          <div>{profile.displayName}</div>
          <div>{profile.email}</div>
        </div>
      )}
    </div>
  )
}

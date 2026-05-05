"use client"

import * as React from "react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { getClient } from "@/utils/data-operations"
import { gravatarAvatarUrl } from "@/utils/user-profile"

const userAuthOptions = { authMode: "userPool" as const }

export type BotAvatarConfig = {
  label: string
  initials: string
  colorClass: string
}

export const botAvatarRegistry: Record<string, BotAvatarConfig> = {
  optimizer: {
    label: "Optimizer Agent",
    initials: "OA",
    colorClass: "bg-info text-info-foreground",
  },
  tactus: {
    label: "Tactus Agent",
    initials: "TA",
    colorClass: "bg-secondary text-secondary-foreground",
  },
  dispatcher: {
    label: "Dispatcher",
    initials: "DP",
    colorClass: "bg-warning text-warning-foreground",
  },
}

export type AttributedUserProfile = {
  id: string
  email: string
  displayName: string
  initials: string
  gravatarUrl: string
}

export type MessageBotAttribution = {
  actorType: "bot"
  actorKey: string
  displayName: string
  avatarKey: string
}

export type ResolvedMessageAttribution =
  | { kind: "user"; userId: string }
  | { kind: "bot"; bot: MessageBotAttribution }
  | { kind: "none" }

function initialsFrom(displayName: string, email: string): string {
  const nameParts = displayName
    .split(/\s+/)
    .map((part) => part.trim())
    .filter(Boolean)

  if (nameParts.length >= 2) {
    return `${nameParts[0][0]}${nameParts[1][0]}`.toUpperCase()
  }

  const source = nameParts[0] || email.split("@")[0] || "User"
  return source.slice(0, 2).toUpperCase()
}

function parseMetadata(value: unknown): Record<string, unknown> | null {
  if (typeof value === "string" && value.trim()) {
    try {
      const parsed = JSON.parse(value)
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch (_error) {
      return null
    }
    return null
  }
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

export function getMessageAttributionMetadata(createdByUserId?: string): Record<string, unknown> {
  return createdByUserId
    ? {
        attribution: {
          actorType: "user",
          userId: createdByUserId,
        },
      }
    : {}
}

export function resolveMessageAttribution(message: {
  role?: string
  createdByUserId?: string | null
  metadata?: unknown
}): ResolvedMessageAttribution {
  const explicitUserId = typeof message.createdByUserId === "string" ? message.createdByUserId.trim() : ""
  if (explicitUserId) {
    return { kind: "user", userId: explicitUserId }
  }

  const parsedMetadata = parseMetadata(message.metadata)
  const attributionRaw = parsedMetadata?.attribution
  if (!attributionRaw || typeof attributionRaw !== "object" || Array.isArray(attributionRaw)) {
    return { kind: "none" }
  }

  const attribution = attributionRaw as Record<string, unknown>
  const actorType = typeof attribution.actorType === "string"
    ? attribution.actorType.trim().toLowerCase()
    : ""

  if (actorType === "user") {
    const userId = typeof attribution.userId === "string" ? attribution.userId.trim() : ""
    if (userId) {
      return { kind: "user", userId }
    }
    return { kind: "none" }
  }

  if (message.role === "USER" && actorType === "bot") {
    const actorKey = typeof attribution.actorKey === "string" && attribution.actorKey.trim()
      ? attribution.actorKey.trim()
      : "bot"
    const displayName = typeof attribution.displayName === "string" && attribution.displayName.trim()
      ? attribution.displayName.trim()
      : "Bot"
    const avatarKey = typeof attribution.avatarKey === "string" && attribution.avatarKey.trim()
      ? attribution.avatarKey.trim()
      : "tactus"
    return {
      kind: "bot",
      bot: {
        actorType: "bot",
        actorKey,
        displayName,
        avatarKey,
      },
    }
  }

  return { kind: "none" }
}

async function fetchAttributedUserProfile(userId: string): Promise<AttributedUserProfile | null> {
  const response = await (getClient().models.User.get as any)(
    { id: userId },
    userAuthOptions,
  )
  const user = response?.data
  const email = typeof user?.email === "string" ? user.email.trim() : ""

  if (!email) {
    return null
  }

  const displayName = typeof user?.displayName === "string" && user.displayName.trim()
    ? user.displayName.trim()
    : email

  return {
    id: userId,
    email,
    displayName,
    initials: initialsFrom(displayName, email),
    gravatarUrl: await gravatarAvatarUrl(email, 64),
  }
}

export function useAttributedUserProfiles(
  userIds: Array<string | null | undefined>,
): Record<string, AttributedUserProfile> {
  const [profilesById, setProfilesById] = React.useState<Record<string, AttributedUserProfile>>({})
  const requestedUserIdsRef = React.useRef<Set<string>>(new Set())

  const userIdKey = Array.from(new Set(
    userIds
      .filter((userId): userId is string => typeof userId === "string" && userId.trim().length > 0)
      .map((userId) => userId.trim()),
  )).sort().join("\u0000")

  const normalizedUserIds = React.useMemo(
    () => (userIdKey ? userIdKey.split("\u0000") : []),
    [userIdKey],
  )

  React.useEffect(() => {
    const missingUserIds = normalizedUserIds.filter((userId) => (
      !profilesById[userId] && !requestedUserIdsRef.current.has(userId)
    ))

    if (missingUserIds.length === 0) {
      return
    }

    let cancelled = false
    missingUserIds.forEach((userId) => requestedUserIdsRef.current.add(userId))

    Promise.all(
      missingUserIds.map(async (userId) => {
        try {
          return await fetchAttributedUserProfile(userId)
        } catch (error) {
          console.warn("Unable to load attributed chat message user:", error)
          return null
        }
      }),
    ).then((profiles) => {
      if (cancelled) {
        return
      }

      const loadedProfiles = profiles.filter((profile): profile is AttributedUserProfile => Boolean(profile))
      if (loadedProfiles.length === 0) {
        return
      }

      setProfilesById((current) => {
        let changed = false
        const next = { ...current }

        for (const profile of loadedProfiles) {
          if (
            next[profile.id]?.email === profile.email
            && next[profile.id]?.displayName === profile.displayName
            && next[profile.id]?.gravatarUrl === profile.gravatarUrl
          ) {
            continue
          }
          next[profile.id] = profile
          changed = true
        }

        return changed ? next : current
      })
    })

    return () => {
      cancelled = true
    }
  }, [normalizedUserIds, profilesById])

  return profilesById
}

export function ChatMessageUserAvatar({
  user,
  className,
}: {
  user: AttributedUserProfile
  className?: string
}) {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Avatar
            aria-label={`Message author: ${user.email}`}
            className={cn("h-7 w-7 bg-muted", className)}
          >
            <AvatarImage
              src={user.gravatarUrl}
              alt={`${user.displayName} avatar`}
              referrerPolicy="no-referrer"
            />
            <AvatarFallback className="bg-muted text-[10px] font-medium uppercase text-muted-foreground">
              {user.initials}
            </AvatarFallback>
          </Avatar>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="center" sideOffset={6} avoidCollisions={false}>
          <p>{user.email}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export function ChatMessageBotAvatar({
  bot,
  className,
}: {
  bot: MessageBotAttribution
  className?: string
}) {
  const registryEntry = botAvatarRegistry[bot.avatarKey]
  const label = bot.displayName || registryEntry?.label || "Bot"
  const initials = (registryEntry?.initials || label.slice(0, 2)).toUpperCase()
  const fallbackClassName = registryEntry?.colorClass || "bg-muted text-muted-foreground"

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Avatar
            aria-label={`Message author: ${label}`}
            className={cn("h-7 w-7", className)}
          >
            <AvatarFallback className={cn("text-[10px] font-medium uppercase", fallbackClassName)}>
              {initials}
            </AvatarFallback>
          </Avatar>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="center" sideOffset={6} avoidCollisions={false}>
          <p>{label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

import { fetchUserAttributes, getCurrentUser } from "aws-amplify/auth"
import { generateClient } from "aws-amplify/data"
import { Sha256 } from "@aws-crypto/sha256-js"
import type { Schema } from "@/amplify/data/resource"

export type CurrentUserProfile = {
  id: string
  email: string
  displayName: string
  initials: string
  gravatarUrl: string | null
}

let amplifyClient: ReturnType<typeof generateClient<Schema>> | null = null
let cachedProfile: CurrentUserProfile | null = null
let pendingProfile: Promise<CurrentUserProfile | null> | null = null

const getAmplifyClient = () => (amplifyClient ??= generateClient<Schema>())

const userAuthOptions = { authMode: "userPool" as const }

function normalizeEmail(email: string): string {
  return email.trim().toLowerCase()
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
}

export async function gravatarHash(email: string): Promise<string> {
  const sha256 = new Sha256()
  sha256.update(normalizeEmail(email))
  return bytesToHex(await sha256.digest())
}

export async function gravatarAvatarUrl(email: string, size = 96): Promise<string> {
  const hash = await gravatarHash(email)
  return `https://www.gravatar.com/avatar/${hash}?s=${size}&d=404&r=g`
}

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

function displayNameFromAttributes(attributes: Record<string, string | undefined>, email: string): string {
  const fullName = attributes.name?.trim()
  if (fullName) return fullName

  const nameParts = [attributes.given_name, attributes.family_name]
    .map((part) => part?.trim())
    .filter(Boolean)
  if (nameParts.length > 0) return nameParts.join(" ")

  return email
}

function emailFromCurrentUser(
  attributes: Record<string, string | undefined>,
  currentUser: Awaited<ReturnType<typeof getCurrentUser>>,
): string | undefined {
  const username = (currentUser as { username?: string }).username
  return (
    attributes.email ||
    currentUser.signInDetails?.loginId ||
    (typeof username === "string" && username.includes("@") ? username : undefined)
  )
}

async function syncUserModelProfile(profile: CurrentUserProfile): Promise<void> {
  const client = getAmplifyClient()
  const now = new Date().toISOString()
  const userPayload = {
    id: profile.id,
    email: profile.email,
    displayName: profile.displayName,
    updatedAt: now,
  }

  const existing = await (client.models.User.get as any)(
    { id: profile.id },
    userAuthOptions,
  )

  if (existing?.data) {
    const existingUser = existing.data
    if (
      existingUser.email !== profile.email ||
      existingUser.displayName !== profile.displayName
    ) {
      await (client.models.User.update as any)(userPayload, userAuthOptions)
    }
    return
  }

  await (client.models.User.create as any)(
    {
      ...userPayload,
      createdAt: now,
    },
    userAuthOptions,
  )
}

export async function getCurrentUserProfile(): Promise<CurrentUserProfile | null> {
  const [currentUser, attributes] = await Promise.all([
    getCurrentUser(),
    fetchUserAttributes(),
  ])

  const id = attributes.sub || currentUser.userId
  const email = emailFromCurrentUser(attributes, currentUser)

  if (!id || !email) {
    return null
  }

  const displayName = displayNameFromAttributes(attributes, email)

  return {
    id,
    email,
    displayName,
    initials: initialsFrom(displayName, email),
    gravatarUrl: await gravatarAvatarUrl(email),
  }
}

export async function ensureCurrentUserProfile(forceRefresh = false): Promise<CurrentUserProfile | null> {
  if (!forceRefresh && cachedProfile) {
    return cachedProfile
  }

  if (!forceRefresh && pendingProfile) {
    return pendingProfile
  }

  pendingProfile = (async () => {
    const profile = await getCurrentUserProfile()
    if (!profile) return null

    cachedProfile = profile

    try {
      await syncUserModelProfile(profile)
    } catch (error) {
      // The profile must still be available even if the User schema is not yet deployed.
      console.warn("Unable to sync User profile record:", error)
    }

    return profile
  })()

  try {
    return await pendingProfile
  } finally {
    pendingProfile = null
  }
}

export async function getCurrentUserAttribution(): Promise<{ createdByUserId?: string }> {
  try {
    const profile = await ensureCurrentUserProfile()
    return profile?.id ? { createdByUserId: profile.id } : {}
  } catch (error) {
    console.warn("Unable to resolve current user attribution:", error)
    return {}
  }
}

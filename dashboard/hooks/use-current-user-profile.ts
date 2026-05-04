"use client"

import { useCallback, useEffect, useState } from "react"
import { useAuthenticator } from "@aws-amplify/ui-react"
import {
  ensureCurrentUserProfile,
  type CurrentUserProfile,
} from "@/utils/user-profile"

type CurrentUserProfileState = {
  profile: CurrentUserProfile | null
  isLoading: boolean
  error: Error | null
  refresh: () => Promise<void>
}

export function useCurrentUserProfile(): CurrentUserProfileState {
  const { authStatus } = useAuthenticator((context) => [context.authStatus])
  const [profile, setProfile] = useState<CurrentUserProfile | null>(null)
  const [isLoading, setIsLoading] = useState(authStatus === "authenticated")
  const [error, setError] = useState<Error | null>(null)

  const loadProfile = useCallback(async (forceRefresh = false) => {
    if (authStatus !== "authenticated") {
      setProfile(null)
      setIsLoading(false)
      setError(null)
      return
    }

    setIsLoading(true)
    try {
      const currentProfile = await ensureCurrentUserProfile(forceRefresh)
      setProfile(currentProfile)
      setError(null)
    } catch (caught) {
      setProfile(null)
      setError(caught instanceof Error ? caught : new Error(String(caught)))
    } finally {
      setIsLoading(false)
    }
  }, [authStatus])

  useEffect(() => {
    let isCancelled = false

    const run = async () => {
      await loadProfile()
      if (isCancelled) {
        return
      }
    }

    void run()

    return () => {
      isCancelled = true
    }
  }, [loadProfile])

  return {
    profile,
    isLoading,
    error,
    refresh: () => loadProfile(true),
  }
}

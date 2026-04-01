"use client"

import * as React from "react"
import type { ConsoleArtifactKind, ConsoleArtifactPayload, ConsoleArtifactState } from "@/components/console/types"

const DEFAULT_WIDTH = 460
const STORAGE_KEY = "plexus-console-artifact-width"

export function useConsoleArtifact() {
  const [state, setState] = React.useState<ConsoleArtifactState>({
    kind: 'none',
    payload: null,
    isOpen: false,
    width: DEFAULT_WIDTH,
  })

  React.useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return

    const parsed = Number(raw)
    if (!Number.isFinite(parsed)) return
    const clamped = Math.max(320, Math.min(900, parsed))
    setState((prev) => ({ ...prev, width: clamped }))
  }, [])

  React.useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, String(state.width))
  }, [state.width])

  const openArtifact = React.useCallback(
    (kind: Exclude<ConsoleArtifactKind, 'none'>, payload: ConsoleArtifactPayload | null = null) => {
      setState((prev) => ({
        ...prev,
        kind,
        payload,
        isOpen: true,
      }))
    },
    []
  )

  const collapseArtifact = React.useCallback(() => {
    setState((prev) => ({
      ...prev,
      isOpen: false,
    }))
  }, [])

  const clearArtifact = React.useCallback(() => {
    setState((prev) => ({
      ...prev,
      kind: 'none',
      payload: null,
      isOpen: false,
    }))
  }, [])

  const setArtifactWidth = React.useCallback((width: number) => {
    setState((prev) => ({
      ...prev,
      width: Math.max(320, Math.min(900, width)),
    }))
  }, [])

  const expandLastArtifact = React.useCallback(() => {
    setState((prev) => {
      if (prev.kind === 'none') {
        return prev
      }
      return {
        ...prev,
        isOpen: true,
      }
    })
  }, [])

  return {
    artifact: state,
    openArtifact,
    collapseArtifact,
    clearArtifact,
    setArtifactWidth,
    expandLastArtifact,
  }
}


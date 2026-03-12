"use client"

import React, { createContext, useContext, useState, useEffect } from 'react'

type SidebarState = 'collapsed' | 'expanded'

interface SidebarContextType {
  rightSidebarState: SidebarState
  setRightSidebarState: React.Dispatch<React.SetStateAction<SidebarState>>
  rightSidebarWidth: number
  setRightSidebarWidth: React.Dispatch<React.SetStateAction<number>>
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined)

const DEFAULT_SIDEBAR_WIDTH = 380
const SIDEBAR_WIDTH_STORAGE_KEY = 'plexus-right-sidebar-width'

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [rightSidebarState, setRightSidebarState] = useState<SidebarState>('collapsed')
  const [rightSidebarWidth, setRightSidebarWidth] = useState<number>(DEFAULT_SIDEBAR_WIDTH)

  // Load saved width from localStorage on mount
  useEffect(() => {
    const savedWidth = localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY)
    if (savedWidth) {
      const width = parseInt(savedWidth, 10)
      if (!isNaN(width)) {
        setRightSidebarWidth(width)
      }
    }
  }, [])

  // Save width to localStorage when it changes
  useEffect(() => {
    localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, rightSidebarWidth.toString())
  }, [rightSidebarWidth])

  return (
    <SidebarContext.Provider value={{
      rightSidebarState,
      setRightSidebarState,
      rightSidebarWidth,
      setRightSidebarWidth
    }}>
      {children}
    </SidebarContext.Provider>
  )
}

export function useSidebar() {
  const context = useContext(SidebarContext)
  if (context === undefined) {
    throw new Error('useSidebar must be used within a SidebarProvider')
  }
  return context
}

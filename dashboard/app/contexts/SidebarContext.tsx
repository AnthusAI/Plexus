"use client"

import React, { createContext, useContext, useState } from 'react'

type SidebarState = 'collapsed' | 'normal' | 'expanded'

interface SidebarContextType {
  rightSidebarState: SidebarState
  setRightSidebarState: React.Dispatch<React.SetStateAction<SidebarState>>
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined)

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [rightSidebarState, setRightSidebarState] = useState<SidebarState>('collapsed')

  return (
    <SidebarContext.Provider value={{ rightSidebarState, setRightSidebarState }}>
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

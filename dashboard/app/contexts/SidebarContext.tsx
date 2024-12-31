"use client"

import React, { createContext, useState, useContext } from 'react'

type SidebarState = 'collapsed' | 'normal' | 'expanded'

interface SidebarContextType {
  rightSidebarState: SidebarState
  setRightSidebarState: React.Dispatch<React.SetStateAction<SidebarState>>
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined)

export const SidebarProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [rightSidebarState, setRightSidebarState] = useState<SidebarState>('collapsed')

  return (
    <SidebarContext.Provider value={{ rightSidebarState, setRightSidebarState }}>
      {children}
    </SidebarContext.Provider>
  )
}

export const useSidebar = () => {
  const context = useContext(SidebarContext)
  if (context === undefined) {
    throw new Error('useSidebar must be used within a SidebarProvider')
  }
  return context
}

'use client'

import React from 'react'
import { Gauge } from 'lucide-react'
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerTrigger,
  DrawerClose,
} from '@/components/ui/drawer'
import { Button } from '@/components/ui/button'
import { ItemsGauges } from '@/components/ItemsGauges'
import { X } from 'lucide-react'

interface DashboardDrawerProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children?: React.ReactNode
}

export function DashboardDrawer({ 
  open, 
  onOpenChange, 
  children 
}: DashboardDrawerProps) {
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      {children && <DrawerTrigger asChild>{children}</DrawerTrigger>}
      <DrawerContent className="max-h-[85vh] border-0 shadow-none">
        <div className="mx-auto w-full max-w-7xl">
          <DrawerHeader className="relative">
            <DrawerTitle className="flex items-center gap-2 text-muted-foreground">
              <Gauge className="h-5 w-5" />
              Dashboard Metrics
            </DrawerTitle>
            <DrawerClose asChild>
              <Button
                variant="ghost"
                size="sm"
                className="absolute right-4 top-4 h-8 w-8 p-0"
              >
                <X className="h-4 w-4" />
                <span className="sr-only">Close</span>
              </Button>
            </DrawerClose>
          </DrawerHeader>
          
          <div className="px-4 pb-6">
            <div className="@container">
              <ItemsGauges />
            </div>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  )
}

// Standalone trigger button component for easy reuse
export function DashboardDrawerTrigger({ 
  open, 
  onOpenChange 
}: { 
  open?: boolean
  onOpenChange?: (open: boolean) => void 
}) {
  return (
    <DashboardDrawer open={open} onOpenChange={onOpenChange}>
      <Button variant="ghost" size="sm" className="gap-2">
        <Gauge className="h-4 w-4" />
        Dashboard
      </Button>
    </DashboardDrawer>
  )
}
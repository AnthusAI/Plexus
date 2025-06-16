'use client'

import React from 'react'
import { Gauge } from 'lucide-react'
import {
  Drawer,
  DrawerContent,
  DrawerTrigger,
} from '@/components/ui/drawer'
import { Button } from '@/components/ui/button'
import { PredictionItemsGauges } from '@/components/PredictionItemsGauges'
import { EvaluationItemsGauges } from '@/components/EvaluationItemsGauges'
import { FeedbackItemsGauges } from '@/components/FeedbackItemsGauges'

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
      <DrawerContent className="max-h-[85vh] max-sm:max-h-[90vh] border-0 shadow-none outline-none ring-0 rounded-t-[2rem] flex flex-col">
        <div className="mx-auto w-full max-w-7xl flex flex-col min-h-0">
          
          <div className="px-4 pt-4 pb-6 space-y-6 overflow-y-auto overflow-x-hidden flex-1">
            {/* Prediction Items Gauges */}
            <div className="@container overflow-visible">
              <PredictionItemsGauges disableEmergenceAnimation={true} />
            </div>
            
            {/* Evaluation Items Gauges */}
            <div className="@container overflow-visible">
              <EvaluationItemsGauges disableEmergenceAnimation={true} />
            </div>
            
            {/* Feedback Items Gauges */}
            <div className="@container overflow-visible">
              <FeedbackItemsGauges disableEmergenceAnimation={true} />
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
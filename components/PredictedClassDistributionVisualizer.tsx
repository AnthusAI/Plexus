import React from 'react'
import { ChartPie } from 'lucide-react'
import ClassDistributionVisualizer, { type ClassDistribution } from './ClassDistributionVisualizer'

interface PredictedClassDistributionVisualizerProps {
  data?: ClassDistribution[]
  rotateThreshold?: number
  hideThreshold?: number
}

export default function PredictedClassDistributionVisualizer({ 
  data = [], 
  rotateThreshold = 8,
  hideThreshold = 4,
}: PredictedClassDistributionVisualizerProps) {
  return (
    <div className="w-full">
      <div className="flex items-start">
        <ChartPie className="w-4 h-4 mr-1 mt-0.5 text-foreground shrink-0" />
        <span className="text-sm text-foreground">Predicted classes</span>
      </div>
      <ClassDistributionVisualizer 
        data={data}
        rotateThreshold={rotateThreshold}
        hideThreshold={hideThreshold}
        isBalanced={null}
        hideHeader={true}
      />
    </div>
  )
} 
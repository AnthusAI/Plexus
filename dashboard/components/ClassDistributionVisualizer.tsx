'use client';

import React from 'react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { 
  SquareSplitHorizontalIcon as SquareSplit, 
  Layers, 
  Scale, 
  EqualNotIcon, 
  SquareMinusIcon, 
  Info 
} from 'lucide-react'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"

export interface ClassDistribution {
  label: string
  count: number
}

interface ClassDistributionVisualizerProps {
  data?: ClassDistribution[]
  rotateThreshold?: number
  hideThreshold?: number
  isBalanced?: boolean | null
  hideHeader?: boolean
  onLabelSelect?: (label: string) => void
}

const getSegmentPosition = (index: number, total: number) => {
  if (total === 1) return 'single'
  if (index === 0) return 'first'
  if (index === total - 1) return 'last'
  return 'middle'
}

export default function ClassDistributionVisualizer({ 
  data = [], 
  rotateThreshold = 8,
  hideThreshold = 4,
  isBalanced = null,
  hideHeader = false,
  onLabelSelect
}: ClassDistributionVisualizerProps) {
  const safeData = Array.isArray(data) ? 
    [...data].sort((a, b) => b.count - a.count) : 
    []
  const classCount = safeData.length
  
  const hasHeader = !hideHeader && (isBalanced !== null || classCount > 0)

  if (!safeData || classCount === 0) {
    return (
      <div className="w-full">
        <div className="relative h-14 rounded-md overflow-hidden">
          <div className="absolute inset-0 bg-pink-100 flex items-center 
            justify-center rounded-md dark:bg-pink-950">
            <span className="text-sm font-medium text-pink-500 
              dark:text-pink-400">No data</span>
          </div>
        </div>
      </div>
    )
  }

  const total = safeData.reduce((sum, item) => sum + item.count, 0)
  const colors = [
    'bg-chart-1',
    'bg-chart-2',
    'bg-chart-3',
    'bg-chart-4',
    'bg-chart-5',
    'bg-chart-6',
    'bg-chart-7',
  ]

  return (
    <TooltipProvider>
      <div className="w-full flex flex-col gap-1">
        {hasHeader && (
          <div className="flex justify-between items-start">
            <div className="flex items-start">
              {classCount === 1 ? (
                <>
                  <SquareMinusIcon className="w-4 h-4 mr-1 mt-0.5 text-foreground 
                    shrink-0" />
                  <span className="text-sm text-foreground">Labels: One class</span>
                </>
              ) : classCount === 2 ? (
                <>
                  <SquareSplit className="w-4 h-4 mr-1 mt-0.5 text-foreground 
                    shrink-0" />
                  <span className="text-sm text-foreground">Labels: Binary</span>
                </>
              ) : (
                <>
                  <Layers className="w-4 h-4 mr-1 mt-0.5 text-foreground shrink-0" />
                  <span className="text-sm text-foreground">Labels: {classCount} classes</span>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button 
                        className="inline-flex items-center"
                        aria-label="Show class list"
                      >
                        <Info className="w-4 h-4 ml-1 mt-0.5 text-foreground shrink-0 
                          cursor-pointer opacity-70 hover:opacity-100" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="max-w-sm bg-background border-0">
                      <div className="space-y-1">
                        <p className="font-medium">Classes:</p>
                        <ul className="text-sm space-y-1">
                          {safeData.map(item => {
                            const percentage = (item.count / total) * 100
                            const roundedPercentage = Math.round(percentage * 10) / 10
                            const displayPercentage = roundedPercentage % 1 === 0 ? 
                              roundedPercentage.toFixed(0) : roundedPercentage.toFixed(1)
                            
                            return (
                              <li key={item.label} className="flex justify-between">
                                <span>{item.label}</span>
                                <span className="text-muted-foreground ml-4">
                                  {item.count} ({displayPercentage}%)
                                </span>
                              </li>
                            )
                          })}
                        </ul>
                      </div>
                    </PopoverContent>
                  </Popover>
                </>
              )}
            </div>
            {isBalanced !== null && classCount > 1 && (
              <div className="flex items-start text-right ml-auto">
                <span className="text-sm mr-1 text-foreground">
                  {isBalanced ? "Balanced distribution" : "Imbalanced distribution"}
                </span>
                {isBalanced ? (
                  <Scale className="w-4 h-4 mt-0.5 text-foreground shrink-0" />
                ) : (
                  <EqualNotIcon className="w-4 h-4 mt-0.5 text-foreground shrink-0" />
                )}
              </div>
            )}
          </div>
        )}
        <div className="relative h-8 rounded-md overflow-visible bg-white 
          dark:bg-card">
          {safeData.map((item, index) => {
            const percentage = (item.count / total) * 100
            const roundedPercentage = Math.round(percentage * 10) / 10
            const displayPercentage = roundedPercentage % 1 === 0 ? 
              roundedPercentage.toFixed(0) : roundedPercentage.toFixed(1)
            const bg = colors[index % colors.length]
            const isSmallSegment = percentage < rotateThreshold
            const shouldHideLabel = percentage < hideThreshold

            const segmentContent = (
              <div className="w-full h-full flex items-center justify-center 
                overflow-visible">
                {!shouldHideLabel && (
                  isSmallSegment ? (
                    <div className="absolute inset-0 flex items-center 
                      justify-center overflow-hidden">
                      <div 
                        className="h-8 flex items-center justify-center"
                        style={{ 
                          transform: 'rotate(-90deg)',
                        }}
                      >
                        <span 
                          className="text-[10px] whitespace-nowrap text-foreground 
                            truncate block px-1"
                          style={{ 
                            maxWidth: '32px',
                          }}
                        >
                          {item.label}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center w-full px-1">
                      <span className="text-sm font-medium text-foreground 
                        leading-tight truncate max-w-full">
                        {item.label}
                      </span>
                    </div>
                  )
                )}
              </div>
            )

            return (
              <Tooltip key={item.label} delayDuration={0}>
                <TooltipTrigger asChild>
                  <div
                    onClick={() => onLabelSelect?.(item.label)}
                    style={{
                      width: `${percentage}%`,
                      left: `${safeData.slice(0, index).reduce((sum, prev) => 
                        sum + (prev.count / total) * 100, 0)}%`
                    }}
                    className={`absolute inset-y-0 ${bg} flex items-center 
                      justify-center overflow-visible cursor-pointer ${
                      getSegmentPosition(index, safeData.length) === 'single' ? 
                        'rounded-md' :
                      getSegmentPosition(index, safeData.length) === 'first' ? 
                        'rounded-l-md' :
                      getSegmentPosition(index, safeData.length) === 'last' ? 
                        'rounded-r-md' : ''
                    }`}
                  >
                    {segmentContent}
                  </div>
                </TooltipTrigger>
                <TooltipContent 
                  side="top" 
                  align="center"
                  sideOffset={5}
                  className="bg-background border-border"
                >
                  <div className="text-center">
                    <p className="font-medium text-foreground">{item.label}</p>
                    <p className="text-foreground">{item.count} ({displayPercentage}%)</p>
                  </div>
                </TooltipContent>
              </Tooltip>
            )
          })}
        </div>
      </div>
    </TooltipProvider>
  )
} 
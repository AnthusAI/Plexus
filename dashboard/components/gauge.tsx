'use client'

import React, { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'

export interface Segment {
  start: number
  end: number
  color: string
}

interface GaugeProps {
  value?: number
  beforeValue?: number
  segments?: Segment[]
  min?: number
  max?: number
  title?: React.ReactNode
  backgroundColor?: string
  showTicks?: boolean
  information?: string
  informationUrl?: string
  priority?: boolean
}

const calculateAngle = (percent: number) => {
  // Use 7π/6 (210 degrees) - halfway between π and 4π/3
  return (percent / 100) * (Math.PI * 7/6)
}

const GaugeComponent: React.FC<GaugeProps> = ({ 
  value, 
  beforeValue,
  segments, 
  min = 0, 
  max = 100,
  title,
  backgroundColor = 'var(--gauge-background)',
  showTicks = false,
  information,
  informationUrl,
  priority = false
}) => {
  const [animatedValue, setAnimatedValue] = useState(0)
  const [animatedBeforeValue, setAnimatedBeforeValue] = useState(0)
  const radius = 80
  const strokeWidth = 25
  const normalizedValue = value !== undefined 
    ? ((value - min) / (max - min)) * 100
    : 0

  const [showInfo, setShowInfo] = useState(false)

  useEffect(() => {
    const startTime = performance.now()
    const duration = 600
    
    const startAngle = animatedValue
    const targetAngle = normalizedValue
    const startBeforeAngle = animatedBeforeValue
    const targetBeforeAngle = beforeValue !== undefined 
      ? ((beforeValue - min) / (max - min)) * 100 
      : null
    
    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime
      const progress = Math.min(elapsed / duration, 1)
      
      const easeProgress = 1 - Math.pow(1 - progress, 3)
      const currentValue = startAngle + (targetAngle - startAngle) * easeProgress
      const currentBeforeValue = startBeforeAngle !== null && targetBeforeAngle !== null
        ? startBeforeAngle + (targetBeforeAngle - startBeforeAngle) * easeProgress
        : null
      
      setAnimatedValue(currentValue)
      setAnimatedBeforeValue(currentBeforeValue ?? 0)
      
      if (progress < 1) {
        requestAnimationFrame(animate)
      }
    }
    
    requestAnimationFrame(animate)
  }, [normalizedValue, beforeValue])

  const calculateCoordinates = (angle: number, r: number = radius) => {
    const x = r * Math.cos(angle - Math.PI / 2)
    const y = r * Math.sin(angle - Math.PI / 2)
    return { x, y }
  }

  const renderSegments = () => {
    return segments?.map((segment, index) => {
      const segmentLength = segment.end - segment.start
      
      // If segment is 50% or less, draw normally
      if (segmentLength <= 50) {
        const startAngle = calculateAngle(segment.start)
        const endAngle = calculateAngle(segment.end)
        const outerStart = calculateCoordinates(startAngle)
        const outerEnd = calculateCoordinates(endAngle)
        const innerStart = calculateCoordinates(startAngle, radius - strokeWidth)
        const innerEnd = calculateCoordinates(endAngle, radius - strokeWidth)

        return (
          <path
            key={index}
            d={`M ${outerStart.x} ${outerStart.y} 
               A ${radius} ${radius} 0 0 1 ${outerEnd.x} ${outerEnd.y}
               L ${innerEnd.x} ${innerEnd.y} 
               A ${radius - strokeWidth} ${radius - strokeWidth} 0 0 0 ${innerStart.x} ${innerStart.y} 
               Z`}
            fill={segment.color}
            stroke="none"
          />
        )
      }

      // For segments > 50%, split into two parts
      const midPoint = segment.start + 50
      const startAngle1 = calculateAngle(segment.start)
      const endAngle1 = calculateAngle(midPoint)
      const startAngle2 = calculateAngle(midPoint)
      const endAngle2 = calculateAngle(segment.end)

      const outerStart1 = calculateCoordinates(startAngle1)
      const outerEnd1 = calculateCoordinates(endAngle1)
      const innerStart1 = calculateCoordinates(startAngle1, radius - strokeWidth)
      const innerEnd1 = calculateCoordinates(endAngle1, radius - strokeWidth)

      const outerStart2 = calculateCoordinates(startAngle2)
      const outerEnd2 = calculateCoordinates(endAngle2)
      const innerStart2 = calculateCoordinates(startAngle2, radius - strokeWidth)
      const innerEnd2 = calculateCoordinates(endAngle2, radius - strokeWidth)

      return (
        <g key={index}>
          <path
            d={`M ${outerStart1.x} ${outerStart1.y} 
               A ${radius} ${radius} 0 0 1 ${outerEnd1.x} ${outerEnd1.y}
               L ${innerEnd1.x} ${innerEnd1.y} 
               A ${radius - strokeWidth} ${radius - strokeWidth} 0 0 0 ${innerStart1.x} ${innerStart1.y} 
               Z`}
            fill={segment.color}
            stroke="none"
          />
          <path
            d={`M ${outerStart2.x} ${outerStart2.y} 
               A ${radius} ${radius} 0 0 1 ${outerEnd2.x} ${outerEnd2.y}
               L ${innerEnd2.x} ${innerEnd2.y} 
               A ${radius - strokeWidth} ${radius - strokeWidth} 0 0 0 ${innerStart2.x} ${innerStart2.y} 
               Z`}
            fill={segment.color}
            stroke="none"
          />
        </g>
      )
    })
  }

  const renderTicks = () => {
    return [...segments || [], { start: 100, end: 100, color: 'transparent' }].map((segment, index) => {
      const angle = calculateAngle(segment.start)
      const { x, y } = calculateCoordinates(angle)
      
      const lineEndX = x * 1.08
      const lineEndY = y * 1.08
      
      const angleInDegrees = (angle * 180) / Math.PI
      const isNearTop = Math.abs(angleInDegrees - 90) < 15
      const verticalAdjustment = isNearTop 
        ? 0.95
        : Math.pow(Math.abs(angleInDegrees - 90) / 90, 0.5) * 0.3
      
      const textOffset = radius + 25 - (verticalAdjustment * 10) + (segment.start === 100 ? 3 : 0)
      
      const textX = textOffset * Math.cos(angle - Math.PI / 2)
      const textY = textOffset * Math.sin(angle - Math.PI / 2)

      return (
        <g key={index}>
          <line
            x1={x}
            y1={y}
            x2={lineEndX}
            y2={lineEndY}
            className="stroke-muted-foreground"
            strokeWidth="0.5"
          />
          <g transform={`translate(${textX} ${textY}) rotate(105)`}>
            <text
              x="0"
              y="0"
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="12"
              className="fill-muted-foreground"
            >
              {segment.start}%
            </text>
          </g>
        </g>
      )
    })
  }

  const topPadding = showTicks ? 104 : 80
  const viewBoxHeight = showTicks ? 200 : 170
  const textY = showTicks ? 45 : 45
  const clipHeight = showTicks ? 168 : 144

  return (
    <div className="flex flex-col items-center w-full h-full max-h-[220px]">
      <div className="relative w-full h-full" style={{ maxWidth: '20em' }}>
        <div className="relative w-full h-full">
          <svg 
            viewBox={`-120 -${topPadding} 240 ${viewBoxHeight}`}
            preserveAspectRatio="xMidYMid meet"
            style={{ 
              width: '100%', 
              height: '100%',
              maxHeight: '100%' 
            }}
          >
            <defs>
              <clipPath id="gaugeClip">
                <rect 
                  x="-120" 
                  y={-topPadding} 
                  width="240" 
                  height={clipHeight} 
                />
              </clipPath>
            </defs>
            <g clipPath="url(#gaugeClip)">
              <circle 
                cx="0" 
                cy="0" 
                r={radius} 
                fill={backgroundColor}
                className="transition-[fill] duration-500 ease-in-out"
              />
              <g transform="rotate(-105)">
                {renderSegments()}
                {showTicks && renderTicks()}
                <g>
                  {beforeValue !== undefined && (
                    <path
                      d={`M 0,-${radius} L -6,0 L 6,0 Z`}
                      className="fill-muted-foreground opacity-40 transition-[fill] duration-500 ease-in-out"
                      transform={`rotate(${(animatedBeforeValue * 210) / 100})`}
                    />
                  )}
                  <path
                    d={`M 0,-${radius} L -6,0 L 6,0 Z`}
                    className={cn(
                      priority ? "fill-focus" : "fill-foreground",
                      value === undefined && "fill-card",
                      "transition-[fill] duration-500 ease-in-out"
                    )}
                    transform={`rotate(${(animatedValue * 210) / 100})`}
                  />
                  <circle 
                    cx="0" 
                    cy="0" 
                    r="10" 
                    className={cn(
                      priority ? "fill-focus" : "fill-foreground",
                      "transition-[fill] duration-500 ease-in-out"
                    )}
                  />
                </g>
              </g>
              <text 
                x="0" 
                y={textY}
                textAnchor="middle" 
                className={cn(
                  "text-[2.25rem] font-bold transition-[fill] duration-500 ease-in-out",
                  priority ? "fill-focus" : "fill-foreground"
                )}
                dominantBaseline="middle"
              >
                {value !== undefined 
                  ? (value % 1 === 0 ? `${value}%` : `${value.toFixed(1)}%`)
                  : ''}
              </text>
            </g>
          </svg>
          {title && (
            <div 
              className={cn(
                "absolute left-1/2 -translate-x-1/2 flex items-center gap-2 whitespace-nowrap",
                "text-[clamp(0.75rem,4vw,1rem)] transition-colors duration-500 ease-in-out",
                priority ? "text-focus" : "text-foreground"
              )}
              style={{
                bottom: showTicks ? '5%' : '2%'
              }}
            >
              {title}
              {information && (
                <button 
                  onClick={() => setShowInfo(!showInfo)} 
                  className="text-muted-foreground hover:text-foreground transition-colors duration-500 ease-in-out"
                  aria-label="Toggle information"
                >
                  <svg 
                    width="16" 
                    height="16" 
                    viewBox="0 0 24 24" 
                    fill="none" 
                    stroke="currentColor" 
                    strokeWidth="2"
                    className="transition-[stroke] duration-500 ease-in-out"
                  >
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4M12 8h.01" />
                  </svg>
                </button>
              )}
            </div>
          )}
        </div>
        {showInfo && information && (
          <div className="w-full text-sm text-left -mt-6 mb-8 pl-4 text-muted-foreground overflow-y-auto max-h-[100px]">
            {information.split('\n\n').map((paragraph, index) => (
              <p key={index} className={index > 0 ? 'mt-4' : ''}>
                {paragraph}
              </p>
            ))}
            {informationUrl && (
              <a 
                href={informationUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline mt-1 block"
              >
                more...
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const defaultSegments = [
  { start: 0, end: 60, color: 'var(--gauge-inviable)' },
  { start: 60, end: 80, color: 'var(--gauge-converging)' },
  { start: 80, end: 90, color: 'var(--gauge-almost)' },
  { start: 90, end: 95, color: 'var(--gauge-viable)' },
  { start: 95, end: 100, color: 'var(--gauge-great)' },
]

export const Gauge: React.FC<GaugeProps> = ({ segments = defaultSegments, ...props }) => {
  return <GaugeComponent segments={segments} {...props} />
}

'use client'

import React, { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { Popover, PopoverContent, PopoverTrigger, PopoverAnchor } from '@/components/ui/popover'
import { CircleHelp } from 'lucide-react'
import NumberFlowWrapper from '@/components/ui/number-flow'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'

export interface Segment {
  start: number
  end: number
  color: string
}

interface GaugeProps {
  value?: number
  beforeValue?: number
  target?: number
  segments?: Segment[]
  min?: number
  max?: number
  title?: React.ReactNode
  backgroundColor?: string
  showTicks?: boolean
  /** 
   * Information text displayed in a popover when the help icon is clicked.
   * Supports full Markdown formatting including:
   * - **bold** and *italic* text
   * - [links](https://example.com)
   * - Lists (bulleted and numbered)
   * - `code` blocks
   * - > blockquotes
   * - Line breaks (use two spaces at end of line)
   */
  information?: string
  informationUrl?: string
  priority?: boolean
  valueFormatter?: (value: number) => string
  valueUnit?: string
  decimalPlaces?: number
  tickSpacingThreshold?: number
  showOnlyEssentialTicks?: boolean
}

const calculateAngle = (percent: number) => {
  // Use 7π/6 (210 degrees) - halfway between π and 4π/3
  // For pegged gauges (105%), extend slightly beyond the normal range
  if (percent > 100) {
    // Map 100-105% to a small extension beyond the normal range
    const overPercent = Math.min(percent - 100, 5) / 5 // 0-1 for 100-105%
    return (Math.PI * 7/6) + (overPercent * (Math.PI * 7/6) * 0.05) // Add 5% more arc
  }
  return (percent / 100) * (Math.PI * 7/6)
}

// Format decimal values without leading zeros for values between -1 and 1
const formatDecimalValue = (value: number, decimalPlaces: number): string => {
  // If it's a whole number, just return the string representation
  if (value % 1 === 0) return value.toString();
  
  // Format to specified decimal places
  const formatted = value.toFixed(decimalPlaces);
  
  // For values between -1 and 1 (but not -1 or 1 exactly), remove leading zero
  if (value > -1 && value < 1 && value !== 0) {
    return formatted.replace(/^(-?)0\./, '$1.');
  }
  
  // Otherwise return the full formatted value
  return formatted;
};

const GaugeComponent: React.FC<GaugeProps> = ({ 
  value, 
  beforeValue,
  target,
  segments, 
  min = 0, 
  max = 100,
  title,
  backgroundColor = 'var(--gauge-background)',
  showTicks = false,
  information,
  informationUrl,
  priority = false,
  valueFormatter,
  valueUnit = '%',
  decimalPlaces = 1,
  tickSpacingThreshold = 5,
  showOnlyEssentialTicks = false
}) => {
  const [animatedValue, setAnimatedValue] = useState(0)
  const [animatedBeforeValue, setAnimatedBeforeValue] = useState(0)
  const [animatedTarget, setAnimatedTarget] = useState(0)
  const [containerWidth, setContainerWidth] = useState(0)
  const containerRef = React.useRef<HTMLDivElement>(null)
  const radius = 80
  const strokeWidth = 25
  const rawNormalizedValue = value !== undefined 
    ? ((value - min) / (max - min)) * 100
    : ((0 - min) / (max - min)) * 100  // When no data, point needle at 0 position
  
  // Check if value is pegged (exceeds max)
  const isPegged = value !== undefined && value > max
  // Cap normalized value at 105% for pegged gauges
  const normalizedValue = isPegged ? 105 : Math.min(rawNormalizedValue, 100)

  useEffect(() => {
    const startTime = performance.now()
    const duration = 600
    
    const startAngle = animatedValue
    const targetAngle = normalizedValue
    const startBeforeAngle = animatedBeforeValue
    const targetBeforeAngle = beforeValue !== undefined 
      ? ((beforeValue - min) / (max - min)) * 100 
      : null
    const startTargetAngle = animatedTarget
    const targetTargetAngle = target !== undefined
      ? ((target - min) / (max - min)) * 100
      : null
    
    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime
      const progress = Math.min(elapsed / duration, 1)
      
      const easeProgress = 1 - Math.pow(1 - progress, 3)
      const currentValue = startAngle + (targetAngle - startAngle) * easeProgress
      const currentBeforeValue = startBeforeAngle !== null && targetBeforeAngle !== null
        ? startBeforeAngle + (targetBeforeAngle - startBeforeAngle) * easeProgress
        : null
      const currentTarget = startTargetAngle !== null && targetTargetAngle !== null
        ? startTargetAngle + (targetTargetAngle - startTargetAngle) * easeProgress
        : null
      
      setAnimatedValue(currentValue)
      setAnimatedBeforeValue(currentBeforeValue ?? 0)
      setAnimatedTarget(currentTarget ?? 0)
      
      if (progress < 1) {
        requestAnimationFrame(animate)
      }
    }
    
    requestAnimationFrame(animate)
  }, [normalizedValue, beforeValue, target])

  useEffect(() => {
    if (!containerRef.current) return

    const updateSize = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth)
      }
    }

    // Initial measurement
    updateSize()

    // Setup resize observer
    const resizeObserver = new ResizeObserver(updateSize)
    resizeObserver.observe(containerRef.current)

    return () => {
      if (containerRef.current) {
        resizeObserver.unobserve(containerRef.current)
      }
    }
  }, [])
  
  // Calculate the offset for the label based on container width
  const getLabelBottomOffset = () => {
    if (containerWidth <= 0) return 0
    
    // Only apply offset when width is below 150px
    if (containerWidth > 150) return 0
    
    // Calculate offset: more offset as it gets smaller
    return Math.max(0, (150 - containerWidth) * 0.1)
  }

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

  const renderTicks = (minValue: number, maxValue: number) => {
    let visibleTicks = new Set<number>();
    
    if (showOnlyEssentialTicks) {
      // Essential ticks mode: only show 0, beforeValue position, and 100 (plus 105 if pegged)
      visibleTicks.add(0);   // Always show the minimum tick
      visibleTicks.add(100); // Always show the maximum tick
      if (isPegged) {
        visibleTicks.add(105); // Always show the pegged tick when over max
      }
      
      // Add the beforeValue (average) position if it exists
      if (beforeValue !== undefined) {
        const beforeValuePercent = ((beforeValue - min) / (max - min)) * 100;
        visibleTicks.add(beforeValuePercent);
      }
    } else {
      // Original logic for segment-based ticks
      // Create an array with all segment starts plus 100, and 105 if pegged
      const baseTicks = [...segments || [], { start: 100, end: 100, color: 'transparent' }]
      if (isPegged) {
        baseTicks.push({ start: 105, end: 105, color: 'transparent' })
      }
      const allTicks = baseTicks
        .map(segment => segment.start)
        .sort((a, b) => a - b); // Sort in ascending order

      // Use the provided threshold for displaying ticks (percentage of total range)
      const thresholdPercentage = tickSpacingThreshold;

      // Filter ticks starting from highest to lowest
      // Keep a tick if it's at least thresholdPercentage away from the next higher tick
      visibleTicks.add(100); // Always show the maximum tick
      visibleTicks.add(0);   // Always show the minimum tick
      if (isPegged) {
        visibleTicks.add(105); // Always show the pegged tick when over max
      }

      // Process remaining ticks from highest to lowest
      for (let i = allTicks.length - 2; i >= 0; i--) {
        const currentTick = allTicks[i];
        const nextHigherTick = allTicks[i + 1]; // The next element is guaranteed to be higher since we sorted
        
        // Skip if this is the minimum tick (0) as we already added it
        if (currentTick === 0) continue;
        
        // If this tick is at least thresholdPercentage away from the next higher tick, show it
        if (nextHigherTick - currentTick >= thresholdPercentage) {
          visibleTicks.add(currentTick);
        }
      }
    }

    // Create ticks to render based on visible ticks
    const ticksToRender = [];
    
    // Add essential ticks
    if (visibleTicks.has(0)) {
      ticksToRender.push({ start: 0, end: 0, color: 'transparent' });
    }
    if (visibleTicks.has(100)) {
      ticksToRender.push({ start: 100, end: 100, color: 'transparent' });
    }
    if (isPegged && visibleTicks.has(105)) {
      ticksToRender.push({ start: 105, end: 105, color: 'transparent' });
    }
    
    // Add beforeValue tick if in essential mode and beforeValue exists
    if (showOnlyEssentialTicks && beforeValue !== undefined) {
      const beforeValuePercent = ((beforeValue - min) / (max - min)) * 100;
      if (visibleTicks.has(beforeValuePercent)) {
        ticksToRender.push({ start: beforeValuePercent, end: beforeValuePercent, color: 'transparent' });
      }
    }
    
    // Add segment-based ticks if not in essential mode
    if (!showOnlyEssentialTicks) {
      const segmentTicks = [...segments || [], { start: 100, end: 100, color: 'transparent' }];
      if (isPegged) {
        segmentTicks.push({ start: 105, end: 105, color: 'transparent' });
      }
      
      for (const segment of segmentTicks) {
        if (visibleTicks.has(segment.start) && !ticksToRender.some(t => t.start === segment.start)) {
          ticksToRender.push(segment);
        }
      }
    }
    
    return ticksToRender
      .map((segment, index) => {
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

        // Calculate the actual value based on min/max
        let tickValue: number
        if (segment.start === 105 && isPegged && value !== undefined) {
          // For the 105% pegged tick, show the actual over-max value
          tickValue = value
        } else {
          tickValue = minValue + (segment.start / 100) * (maxValue - minValue)
        }
        // Format decimal values without leading zeros
        const formattedTickValue = formatDecimalValue(tickValue, decimalPlaces)

        return (
          <g key={index}>
            <line
              x1={x}
              y1={y}
              x2={lineEndX}
              y2={lineEndY}
              className={segment.start === 105 && isPegged ? "stroke-[var(--gauge-great)]" : "stroke-muted-foreground"}
              strokeWidth={segment.start === 105 && isPegged ? "1.5" : "0.5"}
            />
            <g transform={`translate(${textX} ${textY}) rotate(105)`}>
              <text
                x="0"
                y="0"
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize="12"
                className={segment.start === 105 && isPegged ? "fill-[var(--gauge-great)] font-medium" : "fill-muted-foreground"}
              >
                {formattedTickValue}
              </text>
            </g>
          </g>
        )
      })
  }

  const renderTargetTick = () => {
    if (!target || !showTicks) return null
    
    // Calculate the normalized target position (0-100)
    const normalizedTarget = ((target - min) / (max - min)) * 100
    const angle = calculateAngle(normalizedTarget)
    const { x, y } = calculateCoordinates(angle)
    
    const lineEndX = x * 1.08
    const lineEndY = y * 1.08
    
    const angleInDegrees = (angle * 180) / Math.PI
    const isNearTop = Math.abs(angleInDegrees - 90) < 15
    const verticalAdjustment = isNearTop 
      ? 0.95
      : Math.pow(Math.abs(angleInDegrees - 90) / 90, 0.5) * 0.3
    
    const textOffset = radius + 25 - (verticalAdjustment * 10)
    
    const textX = textOffset * Math.cos(angle - Math.PI / 2)
    const textY = textOffset * Math.sin(angle - Math.PI / 2)

    // Format decimal values without leading zeros
    const formattedTargetValue = formatDecimalValue(target, decimalPlaces)

    return (
      <g>
        <line
          x1={x}
          y1={y}
          x2={lineEndX}
          y2={lineEndY}
          className="stroke-primary"
          strokeWidth="1.5"
          strokeDasharray="2,1"
        />
        <g transform={`translate(${textX} ${textY}) rotate(105)`}>
          <text
            x="0"
            y="0"
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize="12"
            className="fill-primary font-medium"
          >
            {formattedTargetValue}
          </text>
        </g>
      </g>
    )
  }

  const topPadding = showTicks ? 124 : 100
  const viewBoxHeight = showTicks ? 240 : 200
  const textY = showTicks ? 65 : 65
  const clipHeight = showTicks ? 184 : 160
  const labelBottomOffset = getLabelBottomOffset()

  // Proportional label positioning: value label always centered, title label always just below arc
  // Value label: flexbox center
  // Title label: top as a percentage of container height, calculated from SVG geometry
  const titleLabelY_svg = radius + strokeWidth / 2 + 8;
  const titleLabelTopPercent = ((titleLabelY_svg + topPadding) / viewBoxHeight) * 100;

  // Cap the maximum rendered circle diameter to 160px (SVG circle is 160 units wide)
  const maxCirclePixelDiameter = 160;
  const circlePixelDiameter = containerWidth > 0 ? Math.min(containerWidth * (2 * radius / 240), maxCirclePixelDiameter) : 0;
  // Font sizes based on the actual circle diameter, with reduced scaling factors (half as tall)
  const valueFontSizePx = circlePixelDiameter * 0.20;
  const titleFontSizePx = circlePixelDiameter * 0.09;

  // Calculate the actual pixel center of the circle
  // SVG viewBox: -120 -topPadding 240 viewBoxHeight
  // Center X: containerWidth / 2
  // Center Y: containerHeight * (topPadding / viewBoxHeight)
  const containerHeight = containerRef.current?.offsetHeight || 0;
  const circleCenterX = containerWidth / 2;
  const circleCenterY = containerHeight * (topPadding / viewBoxHeight);

  // Calculate the top offset for the value label, subtracting half the font size (in viewBox %)
  const valueLabelBaseTop = (radius + strokeWidth / 2 + (showTicks ? 40 : 30)) / viewBoxHeight;
  const valueLabelTop = valueLabelBaseTop - (valueFontSizePx / viewBoxHeight) * 0.5;
  // Calculate the top offset for the title label, using the same base plus a fixed offset and the title font size
  const titleLabelTop = valueLabelBaseTop + 0.195 + (titleFontSizePx / viewBoxHeight) * 0.2;

  // Calculate the pixel Y position of the clipped bottom of the gauge (corrected)
  const clippedBottomY_px = containerHeight > 0 ? containerHeight * (clipHeight / viewBoxHeight) : 0;
  // Position the value label a fixed proportion above the clipped bottom (increase padding)
  const valueLabelY = clippedBottomY_px - (circlePixelDiameter * 0.26);

  return (
    <div className="flex flex-col items-center w-full h-full max-h-[260px] overflow-visible relative">
      <Popover>
        <PopoverAnchor asChild>
          <div ref={containerRef} className="relative w-full h-full overflow-visible" style={{ maxWidth: '20em' }}>
            <div className="relative w-full h-full overflow-visible">
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
                    {showTicks && !target && renderTicks(min, max)}
                    {renderTargetTick()}
                    <g>
                      {beforeValue !== undefined && (
                        <path
                          d={`M 0,-${radius} L -6,0 L 6,0 Z`}
                          className="fill-muted-foreground opacity-40 transition-[fill] duration-500 ease-in-out"
                          transform={`rotate(${(animatedBeforeValue * 210) / 100})`}
                        />
                      )}
                      {target !== undefined && (
                        <path
                          d={`M 0,-${radius} L -6,0 L 6,0 Z`}
                          className="fill-muted-foreground opacity-40 transition-[fill] duration-500 ease-in-out"
                          transform={`rotate(${(animatedTarget * 210) / 100})`}
                        />
                      )}
                      <path
                        d={`M 0,-${radius} L -6,0 L 6,0 Z`}
                        className={cn(
                          isPegged ? "fill-[var(--gauge-great)]" : priority ? "fill-focus" : "fill-foreground",
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

                </g>
              </svg>
              {/* NumberFlow value display positioned over the SVG, using absolutely positioned div */}
              {value !== undefined && (
                <div
                  className={cn(
                    "absolute left-0 right-0 flex justify-center pointer-events-none",
                    priority ? "text-focus" : "text-foreground"
                  )}
                  style={{
                    fontSize: `${valueFontSizePx}px`,
                    top: `${valueLabelY}px`,
                    left: 0,
                    right: 0,
                    overflow: 'visible',
                    '--number-flow-mask-height': '0.1em',
                    textAlign: 'center'
                  } as React.CSSProperties}
                >
                  <span className={cn(
                    "font-bold transition-colors duration-500 ease-in-out"
                  )}>
                    {valueFormatter ? (
                      valueFormatter(value)
                    ) : (
                      <>
                        <NumberFlowWrapper 
                          value={parseFloat(formatDecimalValue(value, decimalPlaces))}
                          format={{ 
                            minimumFractionDigits: value % 1 === 0 ? 0 : decimalPlaces,
                            maximumFractionDigits: decimalPlaces,
                            useGrouping: false
                          }}
                          suffix={valueUnit}
                        />
                      </>
                    )}
                  </span>
                </div>
              )}
              {/* Title label positioned just below the value label, using absolutely positioned div */}
              {title && (
                <div
                  className={cn(
                    "absolute left-0 right-0 flex justify-center items-center whitespace-nowrap",
                    "transition-colors duration-500 ease-in-out",
                    priority ? "text-focus" : "text-muted-foreground"
                  )}
                  style={{
                    fontSize: `${titleFontSizePx}px`,
                    top: `${titleLabelTop * 100}%`, // Optionally, use `${circleCenterY + valueFontSizePx * 0.7}px` for below value label
                    transform: 'translateY(0.2em)',
                    textAlign: 'center'
                  }}
                >
                  <span className="relative flex items-center gap-1">
                    {title}
                    {information && (
                      <PopoverTrigger asChild>
                        <button
                          className="inline-flex items-center justify-center opacity-70 hover:opacity-100"
                          aria-label="More information"
                          style={{ fontSize: `${titleFontSizePx * 0.8}px` }}
                        >
                          <CircleHelp className="h-[1em] w-[1em]" />
                        </button>
                      </PopoverTrigger>
                    )}
                  </span>
                </div>
              )}
            </div>
          </div>
        </PopoverAnchor>
        {information && (
          <PopoverContent className="w-80 text-sm" side="top" align="center">
            <div className="space-y-2">
              <div className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0 text-sm">{children}</p>,
                    ul: ({ children }) => <ul className="mb-2 ml-4 list-disc">{children}</ul>,
                    ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal">{children}</ol>,
                    li: ({ children }) => <li className="mb-1">{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                    em: ({ children }) => <em className="italic">{children}</em>,
                    code: ({ children }) => <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                    pre: ({ children }) => <pre className="bg-muted p-2 rounded overflow-x-auto text-xs">{children}</pre>,
                    h1: ({ children }) => <h1 className="text-base font-semibold mb-2 text-foreground">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-sm font-semibold mb-2 text-foreground">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-sm font-medium mb-1 text-foreground">{children}</h3>,
                    blockquote: ({ children }) => <blockquote className="border-l-4 border-muted-foreground/20 pl-3 italic text-muted-foreground">{children}</blockquote>,
                    a: ({ children, href }) => <a href={href} className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">{children}</a>,
                  }}
                >
                  {information}
                </ReactMarkdown>
              </div>
              {informationUrl && (
                <p>
                  <a
                    href={informationUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline text-xs"
                  >
                    Learn more →
                  </a>
                </p>
              )}
            </div>
          </PopoverContent>
        )}
      </Popover>
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

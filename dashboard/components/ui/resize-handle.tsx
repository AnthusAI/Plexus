"use client"

import React, { useCallback, useEffect, useRef, useState } from 'react'

interface ResizeHandleProps {
  onResize: (width: number) => void
  minWidth: number
  maxWidth: number
  className?: string
}

export function ResizeHandle({
  onResize,
  minWidth,
  maxWidth,
  className = ''
}: ResizeHandleProps) {
  const [isDragging, setIsDragging] = useState(false)
  const handleRef = useRef<HTMLDivElement>(null)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX
      const clampedWidth = Math.min(Math.max(newWidth, minWidth), maxWidth)
      onResize(clampedWidth)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, minWidth, maxWidth, onResize])

  return (
    <div
      ref={handleRef}
      onMouseDown={handleMouseDown}
      className={`
        absolute left-0 top-0 bottom-0 w-1
        cursor-col-resize
        hover:bg-blue-500
        transition-colors duration-150
        ${isDragging ? 'bg-blue-500' : 'bg-transparent'}
        ${className}
      `}
      aria-label="Resize sidebar"
    >
      {/* Visual indicator */}
      <div className="absolute inset-y-0 left-0 w-1 hover:w-1.5 transition-all" />
    </div>
  )
}

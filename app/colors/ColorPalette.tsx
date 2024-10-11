'use client'

import { useState, useEffect } from 'react'
import { Button } from "@/components/ui/button"
import { useTheme } from "next-themes"

const ColorPaletteContent = () => {
  const { resolvedTheme, theme } = useTheme()
  const [mounted, setMounted] = useState(false)

  const colorColumns = [
    [
      'background', 'foreground', 'muted', 'muted-foreground', 'popover',
      'popover-foreground', 'card', 'card-foreground', 'border', 'input'
    ],
    [
      'primary', 'primary-foreground', 'secondary', 'secondary-foreground',
      'accent', 'accent-foreground', 'destructive', 'destructive-foreground',
      'ring', 'user-chat', 'plexus-chat'
    ],
    [
      'chart-1', 'chart-2', 'chart-3', 'chart-4', 'chart-5',
      'chart-6', 'chart-7', 'true', 'false', 'neutral'
    ]
  ]

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    // This effect will run whenever the theme changes
    if (mounted) {
      // Force a re-render
      setMounted(false)
      setTimeout(() => setMounted(true), 0)
    }
  }, [theme, resolvedTheme])

  if (!mounted) {
    return <div>Loading color palette...</div>
  }

  const hslToRgb = (h: number, s: number, l: number): [number, number, number] => {
    s /= 100
    l /= 100
    const k = (n: number) => (n + h / 30) % 12
    const a = s * Math.min(l, 1 - l)
    const f = (n: number) =>
      l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))
    return [255 * f(0), 255 * f(8), 255 * f(4)]
  }

  const calculateLuminance = (hslColor: string): number => {
    console.log(`Calculating luminance for: ${hslColor}`)
    const match = hslColor.match(/hsl\((\d+)deg\s+(\d+(?:\.\d+)?)%\s+(\d+(?:\.\d+)?)%\)/)
    if (!match) {
      console.error(`Invalid HSL color format: ${hslColor}`)
      return 0
    }
    const [, h, s, l] = match.map(Number)
    const [r, g, b] = hslToRgb(h, s, l)
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    console.log(`Calculated luminance: ${luminance}`)
    return luminance
  }

  const getTextColor = (bgColor: string): string => {
    const luminance = calculateLuminance(bgColor)
    const textColor = luminance > 0.5 ? 'text-black' : 'text-white'
    console.log(`Luminance: ${luminance}, Chosen text color: ${textColor}`)
    return textColor
  }

  const getButtonClasses = (color: string) => {
    const baseClasses = "w-full justify-start mb-2 h-auto py-2 border-none"
    const bgClass = `bg-${color}`
    const colorValue = getComputedStyle(document.documentElement)
      .getPropertyValue(`--${color}`).trim()
    const textColor = getTextColor(colorValue)
    return `${baseClasses} ${bgClass} ${textColor}`
  }

  return (
    <div className="container">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {colorColumns.map((column, columnIndex) => (
          <div key={columnIndex}>
            {column.map((color) => (
              <Button
                key={color}
                variant="ghost"
                className={getButtonClasses(color)}
              >
                {color}
              </Button>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

const ColorPalette = () => {
  return <ColorPaletteContent />
}

export default ColorPalette
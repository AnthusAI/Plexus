"use client"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ChevronUp, ChevronDown } from "lucide-react"

interface NumberInputProps {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  className?: string
}

export function NumberInput({ 
  value, 
  onChange, 
  min = 1,
  max = Number.MAX_SAFE_INTEGER,
  className = ""
}: NumberInputProps) {
  const getIncrement = (current: number) => {
    if (current >= 1000) return 1000
    if (current >= 500) return 100
    if (current >= 250) return 50
    return 10
  }

  const handleIncrement = () => {
    const increment = getIncrement(value)
    const newValue = Math.min(value + increment, max)
    onChange(newValue)
  }

  const handleDecrement = () => {
    const currentIncrement = getIncrement(value)
    // If we're at a boundary, we want to step down to the previous increment size
    const decrementSize = value === 1000 ? 100 : 
                         value === 500 ? 50 :
                         value === 250 ? 10 :
                         currentIncrement
    const newValue = Math.max(value - decrementSize, min)
    onChange(newValue)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = parseInt(e.target.value)
    if (isNaN(newValue)) return
    onChange(Math.min(Math.max(newValue, min), max))
  }

  return (
    <div className={`flex items-center ${className}`}>
      <Input
        type="number"
        value={value}
        onChange={handleChange}
        className="[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none font-mono bg-background"
        min={min}
        max={max}
        tabIndex={-1}
      />
      <div className="flex flex-col ml-2">
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          onClick={handleIncrement}
          tabIndex={-1}
        >
          <ChevronUp className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          onClick={handleDecrement}
          tabIndex={-1}
        >
          <ChevronDown className="h-3 w-3" />
        </Button>
      </div>
    </div>
  )
} 
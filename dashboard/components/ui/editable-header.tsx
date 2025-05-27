"use client"
import { useState, useRef, useEffect } from "react"
import { Input } from "./input"
import { Button } from "./button"
import { Pencil, Check, X } from "lucide-react"
import { cn } from "@/lib/utils"

interface EditableHeaderProps {
  value: string
  onChange: (value: string) => void
  className?: string
  level?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6'
  autoFocus?: boolean
}

export function EditableHeader({ 
  value, 
  onChange, 
  className = "", 
  level = 'h2',
  autoFocus = false 
}: EditableHeaderProps) {
  const [isEditing, setIsEditing] = useState(autoFocus)
  const [tempValue, setTempValue] = useState(value)
  const [isHovered, setIsHovered] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditing])

  useEffect(() => {
    setTempValue(value)
  }, [value])

  const handleEditToggle = () => {
    setIsEditing(true)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTempValue(e.target.value)
  }

  const handleSave = () => {
    if (tempValue.trim() !== '') {
      onChange(tempValue)
    } else {
      setTempValue(value) // Reset to original if empty
    }
    setIsEditing(false)
  }

  const handleCancel = () => {
    setTempValue(value)
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSave()
    } else if (e.key === 'Escape') {
      handleCancel()
    }
  }

  // Determine which heading element to render based on level prop
  const HeaderTag = level as keyof JSX.IntrinsicElements

  return (
    <div 
      className="group relative"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {isEditing ? (
        <div className="flex items-center gap-2">
          <Input
            ref={inputRef}
            type="text"
            value={tempValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            className={cn(
              "px-2 py-1 bg-background/50 border border-input focus-visible:ring-1",
              className
            )}
          />
          <div className="flex items-center">
            <Button 
              variant="ghost" 
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={handleSave}
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button 
              variant="ghost" 
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={handleCancel}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-center">
          <HeaderTag className={cn("font-semibold", className)}>
            {value}
          </HeaderTag>
          <Button 
            variant="ghost" 
            size="icon"
            className={cn(
              "h-8 w-8 ml-2 opacity-0 transition-opacity",
              (isHovered || autoFocus) && "opacity-100"
            )}
            onClick={handleEditToggle}
          >
            <Pencil className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
} 
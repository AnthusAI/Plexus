"use client"
import { useState, useRef, useEffect } from "react"
import { Input } from "./input"
import { Button } from "./button"
import { Pencil, Check, X } from "lucide-react"

interface EditableFieldProps {
  value: string
  onChange: (value: string) => void
  className?: string
  autoFocus?: boolean
}

export function EditableField({ 
  value, 
  onChange, 
  className = "", 
  autoFocus = false 
}: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(autoFocus)
  const [tempValue, setTempValue] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if ((isEditing || autoFocus) && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isEditing, autoFocus])

  const handleEditToggle = () => {
    setIsEditing((prev) => !prev)
    setTempValue(value)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTempValue(e.target.value)
  }

  const handleSave = () => {
    onChange(tempValue)
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

  return (
    <div className="flex items-center space-x-2">
      {isEditing ? (
        <>
          <Input
            ref={inputRef}
            type="text"
            value={tempValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            className={`py-1 px-2 ${className}`}
          />
          <Button 
            variant="ghost" 
            size="icon"
            className="h-8 w-8 flex-shrink-0"
            onClick={handleSave}
          >
            <Check className="h-4 w-4" />
          </Button>
          <Button 
            variant="ghost" 
            size="icon"
            className="h-8 w-8 flex-shrink-0"
            onClick={handleCancel}
          >
            <X className="h-4 w-4" />
          </Button>
        </>
      ) : (
        <>
          <span className={`${className}`}>{value}</span>
          <Button 
            variant="ghost" 
            size="icon"
            className="h-8 w-8 flex-shrink-0"
            onClick={handleEditToggle}
          >
            <Pencil className="h-4 w-4" />
          </Button>
        </>
      )}
    </div>
  )
} 
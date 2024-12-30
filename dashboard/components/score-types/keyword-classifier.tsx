'use client'

import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { X } from "lucide-react"

interface KeywordClassifierProps {
  score: any
  onChange: (score: any) => void
}

const exampleKeywords = [
  'child*', 'kid*', 'son', 'daughter', 'niece', 'nephew', 'dependent'
]

export default function KeywordClassifierComponent({ score, onChange }: KeywordClassifierProps) {
  const [keywords, setKeywords] = useState<string[]>(score.keywords || [])

  useEffect(() => {
    if (keywords.length === 0) {
      setKeywords(exampleKeywords)
      onChange({ ...score, keywords: exampleKeywords })
    }
  }, [])

  const addKeyword = (newKeyword: string) => {
    if (newKeyword.trim()) {
      const updatedKeywords = [...keywords, newKeyword.trim()]
      setKeywords(updatedKeywords)
      onChange({ ...score, keywords: updatedKeywords })
    }
  }

  const removeKeyword = (index: number) => {
    const updatedKeywords = keywords.filter((_, i) => i !== index)
    setKeywords(updatedKeywords)
    onChange({ ...score, keywords: updatedKeywords })
  }

  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="newKeyword" className="text-gray-900 dark:text-gray-200">Add Keyword</Label>
        <div className="flex space-x-2">
          <Input
            id="newKeyword"
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                addKeyword((e.target as HTMLInputElement).value)
                ;(e.target as HTMLInputElement).value = ''
              }
            }}
            placeholder="Enter a keyword..."
            className="text-gray-900 dark:text-gray-200"
          />
          <Button onClick={() => {
            const input = document.getElementById('newKeyword') as HTMLInputElement
            addKeyword(input.value)
            input.value = ''
          }}>Add</Button>
        </div>
      </div>
      <div>
        <Label className="text-gray-900 dark:text-gray-200">Current Keywords</Label>
        <div className="flex flex-wrap gap-2 mt-2">
          {keywords.map((keyword, index) => (
            <div key={index} className="flex items-center bg-gray-100 dark:bg-gray-700 rounded-full px-3 py-1">
              <span className="text-gray-900 dark:text-gray-200">{keyword}</span>
              <Button
                variant="ghost"
                size="sm"
                className="ml-2 p-0"
                onClick={() => removeKeyword(index)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

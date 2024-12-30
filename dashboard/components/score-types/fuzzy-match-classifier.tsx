'use client'

import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { X, Plus } from "lucide-react"

interface FuzzyMatchClassifierProps {
  score: any
  onChange: (score: any) => void
}

interface FuzzyPhrase {
  phrase: string
  threshold: number
}

const examplePhrases: FuzzyPhrase[] = [
  { phrase: "child insurance", threshold: 0.8 },
  { phrase: "life policy for kids", threshold: 0.75 },
  { phrase: "family protection plan", threshold: 0.9 }
]

export default function FuzzyMatchClassifierComponent({ score, onChange }: FuzzyMatchClassifierProps) {
  const [phrases, setPhrases] = useState<FuzzyPhrase[]>(score.phrases || [])

  useEffect(() => {
    if (phrases.length === 0) {
      setPhrases(examplePhrases)
      onChange({ ...score, phrases: examplePhrases })
    }
  }, [])

  const addPhrase = () => {
    const newPhrases = [...phrases, { phrase: "", threshold: 0.8 }]
    setPhrases(newPhrases)
    onChange({ ...score, phrases: newPhrases })
  }

  const removePhrase = (index: number) => {
    const updatedPhrases = phrases.filter((_, i) => i !== index)
    setPhrases(updatedPhrases)
    onChange({ ...score, phrases: updatedPhrases })
  }

  const updatePhrase = (index: number, field: 'phrase' | 'threshold', value: string | number) => {
    const updatedPhrases = phrases.map((item, i) => {
      if (i === index) {
        return { ...item, [field]: value }
      }
      return item
    })
    setPhrases(updatedPhrases)
    onChange({ ...score, phrases: updatedPhrases })
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center space-x-2 mb-2">
          <Label className="text-gray-900 dark:text-gray-200 flex-grow">Phrase</Label>
          <Label className="text-gray-900 dark:text-gray-200 w-24 text-center">Threshold</Label>
          <div className="w-8"></div>
        </div>
        <div className="space-y-2">
          {phrases.map((item, index) => (
            <div key={index} className="flex items-center space-x-2">
              <Input
                value={item.phrase}
                onChange={(e) => updatePhrase(index, 'phrase', e.target.value)}
                placeholder="Enter a phrase..."
                className="flex-grow text-gray-900 dark:text-gray-200"
              />
              <Input
                type="number"
                value={item.threshold}
                onChange={(e) => updatePhrase(index, 'threshold', Math.min(1, Math.max(0, parseFloat(e.target.value))))}
                step="0.01"
                min="0"
                max="1"
                className="w-24 text-gray-900 dark:text-gray-200"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removePhrase(index)}
                className="w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>
      <Button onClick={addPhrase} className="mt-2">
        <Plus className="h-4 w-4 mr-2" />
        Add Phrase
      </Button>
    </div>
  )
}

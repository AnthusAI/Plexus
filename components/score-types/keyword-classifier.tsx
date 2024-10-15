import React from 'react'
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface KeywordClassifierProps {
  score: any
  onChange: (score: any) => void
}

export default function KeywordClassifierComponent({ score, onChange }: KeywordClassifierProps) {
  const handleKeywordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...score, keywords: e.target.value.split(',').map(k => k.trim()) })
  }

  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="keywords">Keywords (comma-separated)</Label>
        <Input
          id="keywords"
          value={score.keywords?.join(', ') || ''}
          onChange={handleKeywordChange}
          placeholder="Enter keywords..."
        />
      </div>
      {/* Add more Keyword Classifier specific fields here */}
    </div>
  )
}

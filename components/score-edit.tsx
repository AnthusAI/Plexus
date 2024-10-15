"use client"
import React, { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { X, FlaskConical } from 'lucide-react'

interface ScoreEditProps {
  scorecardId: string
  scoreId: string
}

export default function ScoreEditComponent({ scorecardId, scoreId }: ScoreEditProps) {
  const router = useRouter()
  const [score, setScore] = useState<any>(null)

  useEffect(() => {
    // Fetch the score data here
    // For now, we'll use dummy data
    setScore({
      id: "16732",
      name: "Sample Score",
      scorecardName: "SelectQuote Term Life v1",
      type: "Boolean",
      accuracy: 85,
      aiProvider: "OpenAI",
      aiModel: "gpt-4-mini",
      isFineTuned: false
    })
  }, [scorecardId, scoreId])

  const handleEvaluate = () => {
    // Evaluate the updated score data
    console.log("Evaluating score:", score)
    // Implement evaluation logic here
  }

  const handleCancel = () => {
    router.back()
  }

  if (!score) return <div>Loading...</div>

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex items-center justify-between py-4 px-4 sm:px-6">
        <div>
          <h2 className="text-2xl font-semibold">{score.name}</h2>
          <p className="text-sm text-muted-foreground">{score.scorecardName}</p>
          <p className="text-sm text-muted-foreground mt-1">ID: {score.id}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={handleCancel}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-grow overflow-auto px-4 sm:px-6 pb-4">
        <div className="space-y-4 max-w-2xl">
          <div>
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={score.name}
              onChange={(e) => setScore({ ...score, name: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="type">Type</Label>
            <Select
              value={score.type}
              onValueChange={(value) => setScore({ ...score, type: value })}
            >
              <SelectTrigger id="type">
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Boolean">Boolean</SelectItem>
                <SelectItem value="Numeric">Numeric</SelectItem>
                <SelectItem value="Percentage">Percentage</SelectItem>
                <SelectItem value="Text">Text</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="aiProvider">AI Provider</Label>
            <Input
              id="aiProvider"
              value={score.aiProvider}
              onChange={(e) => setScore({ ...score, aiProvider: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="aiModel">AI Model</Label>
            <Input
              id="aiModel"
              value={score.aiModel}
              onChange={(e) => setScore({ ...score, aiModel: e.target.value })}
            />
          </div>
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="isFineTuned"
              checked={score.isFineTuned}
              onChange={(e) => setScore({ ...score, isFineTuned: e.target.checked })}
            />
            <Label htmlFor="isFineTuned">Fine-tuned</Label>
          </div>
        </div>
      </div>
      <div className="flex justify-end space-x-4 py-4 px-4 sm:px-6">
        <Button variant="outline" onClick={handleCancel}>
          Cancel
        </Button>
        <Button onClick={handleEvaluate}>
          <FlaskConical className="h-4 w-4 mr-2" />
          Evaluate Changes
        </Button>
      </div>
    </div>
  )
}

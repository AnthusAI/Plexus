'use client'

import React, { useState, useEffect } from 'react'
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { PlayCircle } from 'lucide-react'

interface ProgrammaticScoreProps {
  score: any
  onChange: (score: any) => void
}

const defaultPythonCode = `def score(input: ScoreInput) -> ScoreResult:
    return ScoreResult(
        value="Hello, World!",
        explanation="This is a test."
    )`

export default function ProgrammaticScoreComponent({ score, onChange }: ProgrammaticScoreProps) {
  const [pythonCode, setPythonCode] = useState<string>(score.pythonCode || defaultPythonCode)

  useEffect(() => {
    if (!score.pythonCode) {
      onChange({ ...score, pythonCode: defaultPythonCode })
    }
  }, [])

  const handleCodeChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newCode = event.target.value
    setPythonCode(newCode)
    onChange({ ...score, pythonCode: newCode })
  }

  const handleTestCode = () => {
    console.log("Testing code:", pythonCode)
  }

  return (
    <div className="flex flex-col h-full">
      <Label htmlFor="pythonCode" className="text-gray-900 dark:text-gray-200 mb-2">
        Python Code
      </Label>
      <div className="flex-grow relative">
        <Textarea
          id="pythonCode"
          value={pythonCode}
          onChange={handleCodeChange}
          className="font-mono text-sm h-full resize-none text-gray-900 dark:text-gray-200"
          placeholder="Enter your Python code here..."
        />
      </div>
      <div className="flex justify-end mt-4">
        <Button onClick={handleTestCode} className="flex items-center">
          <PlayCircle className="mr-2 h-4 w-4" />
          Test Code
        </Button>
      </div>
    </div>
  )
}

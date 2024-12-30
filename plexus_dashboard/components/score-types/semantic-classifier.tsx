'use client'

import React, { useState } from 'react'
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Brain, BarChart2 } from "lucide-react"

interface SemanticClassifierProps {
  score: any
  onChange: (score: any) => void
}

export default function SemanticClassifierComponent({ score, onChange }: SemanticClassifierProps) {
  const [isTraining, setIsTraining] = useState(false)

  const sampleCount = 1287
  const labelDistribution = {
    "Yes": 731,
    "No": 556
  }

  const handleTrainModel = () => {
    setIsTraining(true)
    // Simulate training process
    setTimeout(() => {
      setIsTraining(false)
      onChange({
        ...score,
        lastTrainedAt: new Date().toISOString(),
        accuracy: 0.89,
        f1Score: 0.91
      })
    }, 3000)
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">Dataset Information</h3>
        <div className="mt-2 space-y-2">
          <p>Total Samples: {sampleCount}</p>
          <div>
            <p>Label Distribution:</p>
            <div className="flex items-center space-x-2 mt-1">
              <Progress value={(labelDistribution.Yes / sampleCount) * 100} className="w-64" />
              <span>Yes: {labelDistribution.Yes} ({((labelDistribution.Yes / sampleCount) * 100).toFixed(1)}%)</span>
            </div>
            <div className="flex items-center space-x-2 mt-1">
              <Progress value={(labelDistribution.No / sampleCount) * 100} className="w-64" />
              <span>No: {labelDistribution.No} ({((labelDistribution.No / sampleCount) * 100).toFixed(1)}%)</span>
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-medium">Model Information</h3>
        <div className="mt-2 space-y-2">
          <p>Model Type: Fine-tuned BERT</p>
          <p>Last Trained: {score.lastTrainedAt ? new Date(score.lastTrainedAt).toLocaleString() : 'Not trained yet'}</p>
          {score.accuracy && <p>Accuracy: {(score.accuracy * 100).toFixed(2)}%</p>}
          {score.f1Score && <p>F1 Score: {score.f1Score.toFixed(2)}</p>}
        </div>
      </div>

      <div>
        <Button 
          onClick={handleTrainModel} 
          disabled={isTraining}
          className="flex items-center"
        >
          {isTraining ? (
            <>
              <Brain className="mr-2 h-4 w-4 animate-pulse" />
              Training...
            </>
          ) : (
            <>
              <Brain className="mr-2 h-4 w-4" />
              Train Model
            </>
          )}
        </Button>
      </div>

      <div>
        <h3 className="text-lg font-medium">Performance Metrics</h3>
        <div className="mt-2 space-y-2">
          <Button variant="outline" className="flex items-center">
            <BarChart2 className="mr-2 h-4 w-4" />
            View Detailed Metrics
          </Button>
        </div>
      </div>
    </div>
  )
}

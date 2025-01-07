"use client"
import React, { useEffect, useState } from 'react'
import type { Schema } from '@/amplify/data/resource'

interface ScoreCountProps {
  scorecard: Schema['Scorecard']['type']
}

export const ScoreCount: React.FC<ScoreCountProps> = ({ scorecard }) => {
  const [count, setCount] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchScoresCount = async () => {
      try {
        setLoading(true)
        let total = 0
        
        // Fetch sections associated with the scorecard
        const sectionsResult = await scorecard.sections()
        const sections = sectionsResult.data || []

        // Iterate through each section to count the scores
        for (const section of sections) {
          let sectionTotal = 0
          let nextToken: string | null = null
          
          do {
            const scoresResult = await section.scores({ nextToken })
            const scores = scoresResult.data || []
            sectionTotal += scores.length
            nextToken = scoresResult.nextToken ?? null
          } while (nextToken)
          
          total += sectionTotal
        }

        setCount(total)
      } catch (err) {
        console.error('Error fetching scores count:', err)
        setError('Failed to load score count.')
      } finally {
        setLoading(false)
      }
    }

    fetchScoresCount()
  }, [scorecard])

  if (loading) {
    return <span>Loading scores...</span>
  }

  if (error) {
    return <span className="text-red-500">{error}</span>
  }

  return <span>{count} Scores</span>
}
"use client"

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2 } from 'lucide-react'

interface SectionStat {
  scorecardName: string;
  sectionCount: number;
}

interface ScoreStat {
  sectionName: string;
  scoreCount: number;
}

interface Stats {
  totalScorecards: number;
  sections: SectionStat[];
  scores: ScoreStat[];
  error?: string;
}

interface TestResult {
  executionTime: number;
  result: Stats | any;
}

interface PerformanceResults {
  oldApproach: TestResult;
  newApproach: TestResult;
  singleScorecard: TestResult;
}

export default function TestPerformancePage() {
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<PerformanceResults | null>(null)
  const [error, setError] = useState<string | null>(null)

  const runTest = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch('/api/test-performance')
      
      if (!response.ok) {
        throw new Error(`Error: ${response.status} ${response.statusText}`)
      }
      
      const data = await response.json()
      setResults(data)
    } catch (err) {
      console.error('Error running performance test:', err)
      setError(err instanceof Error ? err.message : 'An unknown error occurred')
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (ms: number) => {
    return `${ms.toFixed(2)}ms (${(ms / 1000).toFixed(2)}s)`
  }

  const calculateImprovement = () => {
    if (!results) return null
    
    const oldTime = results.oldApproach.executionTime
    const newTime = results.newApproach.executionTime
    
    if (oldTime === 0) return 'N/A'
    
    const improvement = ((oldTime - newTime) / oldTime) * 100
    return `${improvement.toFixed(2)}%`
  }

  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">Scorecard Performance Test</h1>
      
      <div className="mb-6">
        <p className="mb-4">
          This page tests the performance difference between the old and new approaches for fetching scorecard data.
        </p>
        <Button 
          onClick={runTest} 
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Running Test...
            </>
          ) : 'Run Performance Test'}
        </Button>
      </div>
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
          <p><strong>Error:</strong> {error}</p>
        </div>
      )}
      
      {results && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Old Approach</CardTitle>
                <CardDescription>Multiple separate queries with nested loops</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatTime(results.oldApproach.executionTime)}</p>
                <div className="mt-4">
                  <p>Total Scorecards: {results.oldApproach.result.totalScorecards}</p>
                  <p>Total Sections: {results.oldApproach.result.sections?.length || 0}</p>
                  <p>Total Scores: {results.oldApproach.result.scores?.length || 0}</p>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>New Approach</CardTitle>
                <CardDescription>Single comprehensive query</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatTime(results.newApproach.executionTime)}</p>
                <div className="mt-4">
                  <p>Total Scorecards: {results.newApproach.result.totalScorecards}</p>
                  <p>Total Sections: {results.newApproach.result.sections?.length || 0}</p>
                  <p>Total Scores: {results.newApproach.result.scores?.length || 0}</p>
                </div>
              </CardContent>
            </Card>
          </div>
          
          <Card>
            <CardHeader>
              <CardTitle>Performance Improvement</CardTitle>
              <CardDescription>Comparison between old and new approaches</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <h3 className="font-semibold">Old Approach</h3>
                  <p>{formatTime(results.oldApproach.executionTime)}</p>
                </div>
                <div>
                  <h3 className="font-semibold">New Approach</h3>
                  <p>{formatTime(results.newApproach.executionTime)}</p>
                </div>
                <div>
                  <h3 className="font-semibold">Improvement</h3>
                  <p className="text-green-600 font-bold">{calculateImprovement()}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>Single Scorecard Fetch</CardTitle>
              <CardDescription>Performance of fetching a single scorecard with all its data</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{formatTime(results.singleScorecard.executionTime)}</p>
              <div className="mt-4">
                {results.singleScorecard.result.error ? (
                  <p className="text-red-500">{results.singleScorecard.result.error}</p>
                ) : (
                  <>
                    <p>Scorecard: {results.singleScorecard.result.scorecardName}</p>
                    <p>Sections: {results.singleScorecard.result.sectionCount}</p>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
} 
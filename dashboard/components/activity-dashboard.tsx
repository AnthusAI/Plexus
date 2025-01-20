"use client"

import { useState, useMemo, useEffect, useRef, useCallback } from "react"
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent } from "@/components/ui/chart"
import { PieChart, Pie } from "recharts"
import { Progress } from "@/components/ui/progress"
import { Activity, ListTodo, FlaskConical, ArrowRight, Siren, FileText, Sparkles, ChevronLeft, ChevronRight, MoveUpRight, MessageCircleWarning, MessageCircleMore, CalendarIcon, X, Square, RectangleVertical, Loader2 } from "lucide-react"
import { format } from "date-fns"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { TimeRangeSelector } from "@/components/time-range-selector"
import { useInView } from 'react-intersection-observer'
import { useSidebar } from "@/app/contexts/SidebarContext"
import React from "react"
import ScorecardContext from "@/components/ScorecardContext"
import { formatTimeAgo } from '@/utils/format-time'
import { TaskStatus } from '@/types/shared'
import { formatDuration } from '@/utils/format-duration'
import { listRecentActions, observeRecentActions } from '@/utils/data-operations'
import type { Schema } from '@/amplify/data/resource'
import { ActionStageConfig } from '@/components/ui/action-status'

// Import new task components
import EvaluationTaskComponent from '@/components/EvaluationTask'
import AlertTask from '@/components/AlertTask'
import ReportTask from '@/components/ReportTask'
import OptimizationTask from '@/components/OptimizationTask'
import FeedbackTask from '@/components/FeedbackTask'
import ScoreUpdatedTask from '@/components/ScoreUpdatedTask'
import ScoringJobTask from '@/components/ScoringJobTask'

// Import all types from types/tasks
import { 
  ActivityData,
  AlertTaskData,
  FeedbackTaskData,
  OptimizationTaskData,
  ScoreUpdatedTaskData,
  EvaluationTaskData,
  ScoringJobTaskData,
  ReportTaskData,
  isEvaluationActivity,
  EvaluationActivity
} from '@/types/tasks'

function transformActionToActivity(action: Schema['Action']['type']): ActivityData {
  let activityType: ActivityData['type'] = 'Report'  // Default to Report type for now
  if (action.type === 'test') {
    activityType = 'Report'  // We can adjust these mappings as we add more action types
  }

  // Transform stages if present
  const stages = ((action as any).stages || [])
    .sort((a: Schema['ActionStage']['type'], b: Schema['ActionStage']['type']) => a.order - b.order)
    .map((stage: Schema['ActionStage']['type']) => ({
      key: stage.name,
      label: stage.name,
      color: stage.name.toLowerCase() === 'processing' ? 'bg-secondary' : 'bg-primary',
      name: stage.name,
      order: stage.order,
      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      processedItems: stage.processedItems,
      totalItems: stage.totalItems,
      startedAt: stage.startedAt,
      completedAt: stage.completedAt,
      estimatedCompletionAt: stage.estimatedCompletionAt,
      statusMessage: stage.statusMessage
    }))

  // Get current stage info - highest order non-completed stage, or last stage if all completed
  const currentStage = stages.length > 0 ? 
    stages.reduce((current: ActionStageConfig | null, stage: ActionStageConfig) => {
      // If we haven't found a stage yet, use this one
      if (!current) return stage
      
      // If this stage is RUNNING, it should be the current stage
      if (stage.status === 'RUNNING') return stage
      
      // If current stage is RUNNING, keep it
      if (current.status === 'RUNNING') return current
      
      // If neither stage is RUNNING, prefer the earliest PENDING stage
      if (stage.status === 'PENDING' && current.status === 'PENDING') {
        return stage.order < current.order ? stage : current
      }
      
      // If one stage is PENDING and the other isn't, prefer the PENDING stage
      if (stage.status === 'PENDING') return stage
      if (current.status === 'PENDING') return current
      
      // If all stages are completed, use the last one
      if (stage.status === 'COMPLETED' && stage === stages[stages.length - 1] && 
          stages.every((s: ActionStageConfig) => s.order < stage.order ? s.status === 'COMPLETED' : true)) {
        return stage
      }
      
      return current
    }, null) : null

  // Calculate elapsed time based on status
  const elapsedTime = action.startedAt ? formatDuration(
    Math.round(
      (action.status === 'COMPLETED' && action.completedAt ? 
        new Date(action.completedAt).getTime() : 
        new Date().getTime()
      ) - new Date(action.startedAt).getTime()
    ) / 1000
  ) : undefined

  const activity: ActivityData = {
    id: action.id,
    type: activityType,
    scorecard: action.target,
    score: '',
    timestamp: action.createdAt,
    time: formatTimeAgo(new Date(action.createdAt)),
    summary: action.status,
    stages,
    currentStageName: currentStage?.name,
    processedItems: currentStage?.processedItems || 0,
    totalItems: currentStage?.totalItems || 0,
    elapsedTime: elapsedTime,
    estimatedTimeRemaining: action.estimatedCompletionAt 
      ? formatDuration(Math.round((new Date(action.estimatedCompletionAt).getTime() - new Date().getTime()) / 1000))
      : undefined,
    status: action.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
    stageConfigs: stages,
    data: {
      id: action.id,
      title: `${action.type} Action`,
      command: action.command || ''
    }
  }

  return activity
}

const timeToMinutes = (timeString: string): number => {
  const [value, unit] = timeString.toLowerCase().split(' ');
  const numericValue = parseInt(value);
  if (isNaN(numericValue)) return 0;

  switch (unit) {
    case 'm':
    case 'min':
    case 'mins':
    case 'minute':
    case 'minutes':
      return numericValue;
    case 'h':
    case 'hr':
    case 'hrs':
    case 'hour':
    case 'hours':
      return numericValue * 60;
    case 'd':
    case 'day':
    case 'days':
      return numericValue * 1440;
    default:
      if (unit.endsWith('ago')) {
        // Handle cases like "2m ago", "1h ago", etc.
        return timeToMinutes(value + ' ' + unit.slice(0, -3));
      }
      return 0;
  }
}

const barChartData = [
  { name: "Mon", scored: 4, evaluations: 3, analysis: 2, feedback: 1 },
  { name: "Tue", scored: 3, evaluations: 4, analysis: 3, feedback: 2 },
  { name: "Wed", scored: 5, evaluations: 2, analysis: 4, feedback: 1 },
  { name: "Thu", scored: 2, evaluations: 5, analysis: 1, feedback: 3 },
  { name: "Fri", scored: 3, evaluations: 3, analysis: 3, feedback: 2 },
  { name: "Sat", scored: 1, evaluations: 2, analysis: 2, feedback: 1 },
  { name: "Sun", scored: 4, evaluations: 1, analysis: 5, feedback: 2 },
]

const chartConfig = {
  scored: { label: "Scored", color: "var(--chart-1)" },
  evaluations: { label: "Evaluations", color: "var(--chart-2)" },
  analysis: { label: "Analysis", color: "var(--chart-3)" },
  feedback: { label: "Feedback", color: "var(--chart-4)" },
  positive: { label: "Positive", color: "var(--true)" },
  negative: { label: "Negative", color: "var(--false)" },
}

interface BarData {
  name: string;
  scored: number;
  evaluations: number;
  analysis: number;
  feedback: number;
  [key: string]: string | number;
}

export default function ActivityDashboard() {
  const [selectedBar, setSelectedBar] = useState<BarData | null>(null)
  const [selectedActivity, setSelectedActivity] = useState<ActivityData | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [displayedActivities, setDisplayedActivities] = useState<ActivityData[]>([])
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [recentActions, setRecentActions] = useState<Schema['Action']['type'][]>([])
  const { ref, inView } = useInView({
    threshold: 0,
    rootMargin: '0px 0px 400px 0px',
  })

  useEffect(() => {
    const subscription = observeRecentActions(12).subscribe({
      next: ({ items, isSynced }) => {
        console.log('Received actions update:', { 
          count: items.length, 
          isSynced,
          firstId: items[0]?.id,
          lastId: items[items.length - 1]?.id
        })
        setRecentActions(items)
      },
      error: (error) => {
        console.error('Error observing actions:', error)
      }
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [])

  const activityListRef = useRef<HTMLDivElement>(null)
  const { rightSidebarState } = useSidebar()

  useEffect(() => {
    const transformed = recentActions.map(transformActionToActivity)
    console.log('Transformed actions:', transformed)
    setDisplayedActivities(transformed)
    setIsInitialLoading(false)
  }, [recentActions])

  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }

    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)

    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  useEffect(() => {
    if (selectedActivity && activityListRef.current) {
      const selectedCard = activityListRef.current.querySelector(
        `[data-activity-id="${selectedActivity.id}"]`
      )
      if (selectedCard) {
        selectedCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }
    }
  }, [selectedActivity])

  const handleBarClick = (data: BarData, index: number) => {
    setSelectedBar({ ...data, index })
  }

  const renderActivityIcon = (type: string) => {
    switch (type) {
      case "Evaluation completed":
      case "Evaluation started":
        return <FlaskConical className="h-6 w-6" />
      case "Optimization started":
        return <Sparkles className="h-6 w-6" />
      case "Score updated":
        return <ListTodo className="h-6 w-6" />
      case "Alert":
        return <Siren className="h-6 w-6" />
      case "Report":
        return <FileText className="h-6 w-6" />
      case "Feedback queue started":
      case "Feedback queue completed":
        return <MessageCircleMore className="h-6 w-6" />
      default:
        return <Activity className="h-6 w-6" />
    }
  }

  const renderVisualization = (activity: ActivityData) => {
    switch (activity.type) {
      case "Evaluation completed":
      case "Evaluation started":
        if (isEvaluationActivity(activity)) {
          const accuracy = activity.data.accuracy ?? 0
          const processedItems = activity.data.processedItems ?? 0
          const totalItems = activity.data.totalItems ?? 0
          
          return (
            <ChartContainer config={chartConfig} className="h-[120px] w-[120px] mx-auto mb-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Pie
                    data={[
                      { 
                        category: 'Correct', 
                        value: Math.round(processedItems * accuracy / 100),
                        fill: "var(--true)"
                      },
                      { 
                        category: 'Incorrect', 
                        value: processedItems - Math.round(processedItems * accuracy / 100),
                        fill: "var(--false)"
                      }
                    ]}
                    dataKey="value"
                    nameKey="category"
                    outerRadius={40}
                  />
                  <Pie
                    data={[
                      { category: 'Processed', value: processedItems, fill: "var(--true)" },
                      { category: 'Remaining', value: totalItems - processedItems, fill: "var(--neutral)" }
                    ]}
                    dataKey="value"
                    nameKey="category"
                    innerRadius={45}
                    outerRadius={55}
                  />
                </PieChart>
              </ResponsiveContainer>
            </ChartContainer>
          )
        }
        return null
      case "Score updated":
        return (
          <div className="flex space-x-4 justify-center mb-4">
            <div className="text-center">
              <div className="text-sm font-medium mb-1">Before</div>
              <ChartContainer config={chartConfig} className="h-[80px] w-[80px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Pie
                      data={activity.data?.before?.innerRing}
                      dataKey="value"
                      nameKey="category"
                      outerRadius={30}
                      fill="var(--chart-1)"
                    />
                    <Pie
                      data={activity.data?.before?.outerRing}
                      dataKey="value"
                      nameKey="category"
                      innerRadius={35}
                      outerRadius={40}
                      fill="var(--chart-2)"
                    />
                  </PieChart>
                </ResponsiveContainer>
              </ChartContainer>
            </div>
            <div className="text-center">
              <div className="text-sm font-medium mb-1">After</div>
              <ChartContainer config={chartConfig} className="h-[80px] w-[80px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Pie
                      data={activity.data?.after?.innerRing}
                      dataKey="value"
                      nameKey="category"
                      outerRadius={30}
                      fill="var(--chart-1)"
                    />
                    <Pie
                      data={activity.data?.after?.outerRing}
                      dataKey="value"
                      nameKey="category"
                      innerRadius={35}
                      outerRadius={40}
                      fill="var(--chart-2)"
                    />
                  </PieChart>
                </ResponsiveContainer>
              </ChartContainer>
            </div>
          </div>
        )
      default:
        return null
    }
  }

  const ACTIVITY_TIME_RANGE_OPTIONS = [
    { value: "recent", label: "Recent" },
    { value: "24h", label: "Last 24 hours" },
    { value: "7d", label: "Last 7 days" },
    { value: "30d", label: "Last 30 days" },
    { value: "custom", label: "Custom" },
  ]

  const handleTimeRangeChange = (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => {
    console.log("Time range changed:", range, customRange)
    // Implement the logic for handling all default time ranges and custom date ranges
  }

  const DetailViewControlButtons = (
    <Button variant="outline" size="icon" onClick={() => setSelectedActivity(null)}>
      <X className="h-4 w-4" />
    </Button>
  )

  const containerRef = useRef<HTMLDivElement>(null)
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const [chartDimensions, setChartDimensions] = useState({ width: 0, height: 300 })

  useEffect(() => {
    const updateDimensions = () => {
      if (chartContainerRef.current) {
        setChartDimensions({
          width: chartContainerRef.current.offsetWidth,
          height: 300 // You can make this dynamic too if needed
        })
      }
    }

    updateDimensions()
    window.addEventListener('resize', updateDimensions)

    return () => window.removeEventListener('resize', updateDimensions)
  }, [])

  const availableFields = [
    { value: 'SelectQuote Term Life v1', label: 'SelectQuote Term Life v1' },
    { value: 'CS3 Nexstar v1', label: 'CS3 Nexstar v1' },
    { value: 'CS3 Services v2', label: 'CS3 Services v2' },
    { value: 'CS3 Audigy', label: 'CS3 Audigy' },
    { value: 'AW IB Sales', label: 'AW IB Sales' },
  ]

  const scoreOptions = [
    { value: 'Good Call', label: 'Good Call' },
    { value: 'Agent Branding', label: 'Agent Branding' },
    { value: 'Temperature Check', label: 'Temperature Check' },
    { value: 'Assumptive Close', label: 'Assumptive Close' },
  ]

  const [leftPanelWidth, setLeftPanelWidth] = useState<number>(67) // Start at roughly 2/3
  const dragStateRef = useRef<{
    isDragging: boolean
    startX: number
    startWidth: number
  }>({
    isDragging: false,
    startX: 0,
    startWidth: 67
  })

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragStateRef.current = {
      isDragging: true,
      startX: e.clientX,
      startWidth: leftPanelWidth
    }
    document.addEventListener('mousemove', handleDragMove)
    document.addEventListener('mouseup', handleDragEnd)
  }, [leftPanelWidth])

  const handleDragMove = useCallback((e: MouseEvent) => {
    if (!dragStateRef.current.isDragging || !containerRef.current) return

    const containerWidth = containerRef.current.offsetWidth
    const deltaX = e.clientX - dragStateRef.current.startX
    const newWidthPercent = (dragStateRef.current.startWidth * 
      containerWidth / 100 + deltaX) / containerWidth * 100

    // Constrain width between 20% and 80%
    const constrainedWidth = Math.min(Math.max(newWidthPercent, 20), 80)
    setLeftPanelWidth(constrainedWidth)
  }, [])

  const handleDragEnd = useCallback(() => {
    dragStateRef.current.isDragging = false
    document.removeEventListener('mousemove', handleDragMove)
    document.removeEventListener('mouseup', handleDragEnd)
  }, [])

  return (
    <div className="h-full flex" ref={containerRef}>
      {/* Left side with chart and activities */}
      <div 
        className="@container overflow-y-auto"
        style={{ width: selectedActivity && !isNarrowViewport ? `${leftPanelWidth}%` : '100%' }}
      >
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <ScorecardContext 
              selectedScorecard={selectedScorecard}
              setSelectedScorecard={setSelectedScorecard}
              selectedScore={selectedScore}
              setSelectedScore={setSelectedScore}
            />
            <TimeRangeSelector 
              onTimeRangeChange={handleTimeRangeChange}
              options={ACTIVITY_TIME_RANGE_OPTIONS}
            />
          </div>

          {/* Temporarily disabled bar chart */}
          {/* <Card className="shadow-none border-none mb-6 bg-card">
            <CardContent className="p-0">
              <div ref={chartContainerRef} className="w-full h-[300px]">
                <ChartContainer config={chartConfig} className="h-full w-full">
                  <BarChart 
                    data={barChartData} 
                    width={chartDimensions.width} 
                    height={chartDimensions.height}
                    margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                  >
                    <XAxis dataKey="name" />
                    <YAxis />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar
                      dataKey="scored"
                      stackId="a"
                      fill="var(--chart-1)"
                      onClick={handleBarClick}
                      cursor="pointer"
                    />
                    <Bar
                      dataKey="evaluations"
                      stackId="a"
                      fill="var(--chart-2)"
                      onClick={handleBarClick}
                      cursor="pointer"
                    />
                    <Bar
                      dataKey="analysis"
                      stackId="a"
                      fill="var(--chart-3)"
                      onClick={handleBarClick}
                      cursor="pointer"
                    />
                    <Bar
                      dataKey="feedback"
                      stackId="a"
                      fill="var(--chart-4)"
                      onClick={handleBarClick}
                      cursor="pointer"
                      radius={[6, 6, 0, 0]}
                    />
                    <ChartLegend content={<ChartLegendContent />} />
                  </BarChart>
                </ChartContainer>
              </div>
            </CardContent>
          </Card> */}

          <div className="grid gap-2 pb-8 grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3">
            {displayedActivities.map((activity) => (
              <div key={activity.id} className="w-full">
                {(() => {
                  switch (activity.type) {
                    case 'Scoring Job':
                      return (
                        <ScoringJobTask
                          variant="grid"
                          task={{
                            ...activity,
                            data: {
                              ...activity.data,
                              status: activity.data?.status || 'pending',
                              completedItems: activity.data?.completedItems || 0,
                              totalItems: activity.data?.totalItems || 0
                            }
                          }}
                          onClick={() => setSelectedActivity(activity)}
                        />
                      )
                    case 'Evaluation completed':
                    case 'Evaluation started':
                      return isEvaluationActivity(activity) ? (
                        <EvaluationTaskComponent
                          variant="grid"
                          task={{
                            ...activity,
                            data: {
                              ...activity.data,
                              metrics: [
                                {
                                  name: "Accuracy",
                                  value: activity.data.accuracy ?? 0,
                                  unit: "%",
                                  maximum: 100,
                                  priority: true
                                }
                              ]
                            }
                          }}
                          onClick={() => setSelectedActivity(activity)}
                          onToggleFullWidth={() => {}}
                          onClose={() => {}}
                        />
                      ) : null
                    case 'Alert':
                      return (
                        <AlertTask 
                          variant="grid" 
                          task={{
                            ...activity,
                            data: {
                              ...activity.data,
                              iconType: 'warning' as const
                            }
                          }}
                          onClick={() => setSelectedActivity(activity)}
                          onToggleFullWidth={() => {}}
                          onClose={() => {}}
                        />
                      )
                    case 'Report':
                      return (
                        <ReportTask
                          variant="grid"
                          task={activity}
                          onClick={() => setSelectedActivity(activity)}
                          onToggleFullWidth={() => {}}
                          onClose={() => {}}
                        />
                      )
                    case 'Optimization started':
                      if (!selectedActivity) return null;
                      const optimizationData = selectedActivity.data as OptimizationTaskData;
                      return (
                        <OptimizationTask
                          variant="detail"
                          task={{
                            id: selectedActivity.id,
                            type: selectedActivity.type,
                            scorecard: selectedActivity.scorecard,
                            score: selectedActivity.score,
                            time: selectedActivity.time,
                            summary: selectedActivity.summary,
                            description: selectedActivity.description,
                            data: {
                              progress: optimizationData.progress,
                              accuracy: optimizationData.accuracy,
                              numberComplete: optimizationData.numberComplete,
                              numberTotal: optimizationData.numberTotal,
                              eta: optimizationData.eta,
                              processedItems: optimizationData.processedItems,
                              totalItems: optimizationData.totalItems,
                              before: optimizationData.before,
                              after: optimizationData.after,
                              elapsedTime: formatDuration(optimizationData.elapsedSeconds ?? 0),
                              estimatedTimeRemaining: formatDuration(optimizationData.estimatedRemainingSeconds ?? 0),
                              id: optimizationData.id,
                              title: optimizationData.title,
                              elapsedSeconds: optimizationData.elapsedSeconds,
                              estimatedRemainingSeconds: optimizationData.estimatedRemainingSeconds
                            }
                          }}
                          isFullWidth={isFullWidth}
                          onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                          onClose={() => {
                            setSelectedActivity(null)
                            setIsFullWidth(false)
                          }}
                        />
                      )
                    case 'Feedback queue started':
                    case 'Feedback queue completed':
                      return (
                        <FeedbackTask
                          variant="grid"
                          task={activity}
                          onClick={() => setSelectedActivity(activity)}
                          onToggleFullWidth={() => {}}
                          onClose={() => {}}
                        />
                      )
                    case 'Score updated':
                      return (
                        <ScoreUpdatedTask 
                          variant="grid" 
                          task={activity}
                          onClick={() => setSelectedActivity(activity)}
                          onToggleFullWidth={() => {}}
                          onClose={() => {}}
                        />
                      )
                    default:
                      return null
                  }
                })()}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Resize handle */}
      {selectedActivity && !isNarrowViewport && !isFullWidth && (
        <div
          className="w-2 relative cursor-col-resize flex-shrink-0 group"
          onMouseDown={handleDragStart}
        >
          <div className="absolute inset-0 rounded-full transition-colors duration-150 
            group-hover:bg-accent" />
        </div>
      )}

      {/* Right side detail view */}
      {selectedActivity && !isNarrowViewport && (
        <div 
          className={`${isFullWidth ? 'w-full' : ''} overflow-y-auto`}
          style={!isFullWidth ? { width: `${100 - leftPanelWidth}%` } : undefined}
        >
          <div className="">
            <div className="" />
            {(() => {
              switch (selectedActivity.type) {
                case 'Evaluation completed':
                case 'Evaluation started':
                  return isEvaluationActivity(selectedActivity) ? (
                    <EvaluationTaskComponent 
                      variant="detail" 
                      task={selectedActivity} 
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  ) : null
                case 'Alert':
                  return (
                    <AlertTask 
                      variant="detail" 
                      task={{
                        ...selectedActivity,
                        data: {
                          ...selectedActivity.data,
                          iconType: 'warning' as const
                        }
                      }}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Scoring Job':
                  return (
                    <ScoringJobTask 
                      variant="detail" 
                      task={selectedActivity}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Optimization started':
                  return (
                    <OptimizationTask
                      variant="detail"
                      task={{
                        ...selectedActivity,
                        data: {
                          ...selectedActivity.data,
                          elapsedTime: formatDuration(selectedActivity.data?.elapsedSeconds || 0),
                          estimatedTimeRemaining: formatDuration(selectedActivity.data?.estimatedRemainingSeconds || 0),
                          elapsedSeconds: selectedActivity.data?.elapsedSeconds || 0,
                          estimatedRemainingSeconds: selectedActivity.data?.estimatedRemainingSeconds || 0
                        }
                      }}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Report':
                  return (
                    <ReportTask 
                      variant="detail" 
                      task={selectedActivity}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Feedback queue started':
                case 'Feedback queue completed':
                  return (
                    <FeedbackTask 
                      variant="detail" 
                      task={selectedActivity}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Score updated':
                  return (
                    <ScoreUpdatedTask 
                      variant="detail" 
                      task={selectedActivity}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                default:
                  return null
              }
            })()}
          </div>
        </div>
      )}

      {/* Mobile view */}
      {selectedActivity && isNarrowViewport && (
        <div className="fixed inset-0 bg-background/80 z-50">
          <div className="container flex items-center justify-center h-full max-w-lg">
            {(() => {
              switch (selectedActivity.type) {
                case 'Evaluation completed':
                case 'Evaluation started':
                  return isEvaluationActivity(selectedActivity) ? (
                    <EvaluationTaskComponent 
                      variant="detail" 
                      task={selectedActivity} 
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  ) : null
                case 'Alert':
                  return (
                    <AlertTask 
                      variant="detail" 
                      task={{
                        ...selectedActivity,
                        data: {
                          ...selectedActivity.data,
                          iconType: 'warning' as const
                        }
                      }}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Scoring Job':
                  return (
                    <ScoringJobTask 
                      variant="detail" 
                      task={selectedActivity}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Optimization started':
                  return (
                    <OptimizationTask
                      variant="detail"
                      task={{
                        ...selectedActivity,
                        data: {
                          ...selectedActivity.data,
                          elapsedTime: formatDuration(selectedActivity.data?.elapsedSeconds || 0),
                          estimatedTimeRemaining: formatDuration(selectedActivity.data?.estimatedRemainingSeconds || 0),
                          elapsedSeconds: selectedActivity.data?.elapsedSeconds || 0,
                          estimatedRemainingSeconds: selectedActivity.data?.estimatedRemainingSeconds || 0
                        }
                      }}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Report':
                  return (
                    <ReportTask 
                      variant="detail" 
                      task={selectedActivity}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Feedback queue started':
                case 'Feedback queue completed':
                  return (
                    <FeedbackTask 
                      variant="detail" 
                      task={selectedActivity}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                case 'Score updated':
                  return (
                    <ScoreUpdatedTask 
                      variant="detail" 
                      task={selectedActivity}
                      isFullWidth={isFullWidth}
                      onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                      onClose={() => {
                        setSelectedActivity(null)
                        setIsFullWidth(false)
                      }}
                    />
                  )
                default:
                  return null
              }
            })()}
          </div>
        </div>
      )}
    </div>
  )
}

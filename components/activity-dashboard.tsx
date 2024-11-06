"use client"

import { useState, useMemo, useEffect, useRef, useCallback } from "react"
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent } from "@/components/ui/chart"
import { PieChart, Pie } from "recharts"
import { Progress } from "@/components/ui/progress"
import { Activity, ListTodo, FlaskConical, ArrowRight, Siren, FileText, Sparkles, ChevronLeft, ChevronRight, MoveUpRight, MessageCircleWarning, MessageCircleMore, CalendarIcon, X, Square, Columns2, Loader2 } from "lucide-react"
import { format } from "date-fns"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { TimeRangeSelector } from "@/components/time-range-selector"
import { useInView } from 'react-intersection-observer'
import { useSidebar } from "@/app/contexts/SidebarContext"
import React from "react"
import ScorecardContext from "@/components/ScorecardContext"

// Import new task components
import ExperimentTaskComponent from '@/components/ExperimentTask'
import AlertTask from '@/components/AlertTask'
import ReportTask from '@/components/ReportTask'
import OptimizationTask from '@/components/OptimizationTask'
import FeedbackTask from '@/components/FeedbackTask'
import ScoreUpdatedTask from '@/components/ScoreUpdatedTask'

// Import the type from ExperimentTask
import type { ExperimentTask } from '@/components/ExperimentTask'

interface OptimizationTask {
  id: number
  type: 'Optimization started'
  scorecard: string
  score: string
  time: string
  summary: string
  description?: string
  data: {
    progress: number
    accuracy: number
    elapsedTime: string
    estimatedTimeRemaining: string
    numberComplete: number
    numberTotal: number
    before: {
      outerRing: Array<{ category: string; value: number; fill: string }>
      innerRing: Array<{ category: string; value: number; fill: string }>
    }
    after: {
      outerRing: Array<{ category: string; value: number; fill: string }>
      innerRing: Array<{ category: string; value: number; fill: string }>
    }
  }
}

interface FeedbackTask {
  id: number
  type: 'Feedback queue started' | 'Feedback queue completed'
  scorecard: string
  score: string
  time: string
  summary: string
  description?: string
  data: {
    progress: number
    processedItems: number
    totalItems: number
    elapsedTime: string
    estimatedTimeRemaining: string
  }
}

interface AlertTask {
  id: number
  type: 'Alert'
  scorecard: string
  score: string
  time: string
  summary: string
  description?: string
}

interface ReportTask {
  id: number
  type: 'Report'
  scorecard: string
  score: string
  time: string
  summary: string
  description?: string
}

interface ScoreUpdatedTask {
  id: number
  type: 'Score updated'
  scorecard: string
  score: string
  time: string
  summary: string
  description?: string
  data: {
    before: {
      outerRing: Array<{ category: string; value: number; fill: string }>
      innerRing: Array<{ category: string; value: number; fill: string }>
    }
    after: {
      outerRing: Array<{ category: string; value: number; fill: string }>
      innerRing: Array<{ category: string; value: number; fill: string }>
    }
  }
}

type ActivityData = 
  | ExperimentTask 
  | OptimizationTask 
  | FeedbackTask 
  | AlertTask 
  | ReportTask 
  | ScoreUpdatedTask

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
  { name: "Mon", scored: 4, experiments: 3, analysis: 2, feedback: 1 },
  { name: "Tue", scored: 3, experiments: 4, analysis: 3, feedback: 2 },
  { name: "Wed", scored: 5, experiments: 2, analysis: 4, feedback: 1 },
  { name: "Thu", scored: 2, experiments: 5, analysis: 1, feedback: 3 },
  { name: "Fri", scored: 3, experiments: 3, analysis: 3, feedback: 2 },
  { name: "Sat", scored: 1, experiments: 2, analysis: 2, feedback: 1 },
  { name: "Sun", scored: 4, experiments: 1, analysis: 5, feedback: 2 },
]

// New data for recent activities
const recentActivities: ActivityData[] = [
  {
    id: 0,
    type: "Experiment started",
    scorecard: "CS3 Services v2",
    score: "Good Call",
    time: "2m ago",
    description: "Note",
    summary: '\"Using fine-tuned model.\"',
    data: {
      accuracy: 89,
      sensitivity: 87,
      specificity: 91,
      precision: 88,
      processedItems: 47,
      totalItems: 100,
      elapsedTime: "00:02:15",
      estimatedTimeRemaining: "00:03:05",
      confusionMatrix: {
        matrix: [
          [21, 2, 1],
          [1, 19, 1],
          [0, 1, 18],
        ],
        labels: ["Yes", "No", "NA"],
      },
    },
  },
  {
    id: 1,
    type: "Alert",
    scorecard: "Prime Edu",
    score: "Agent Branding",
    time: "15m ago",
    summary: "Inappropriate content detected",
    description: "Score above 1 in the previous 15 minutes",
  },
  {
    id: 2,
    type: "Report",
    scorecard: "SelectQuote TermLife v1",
    score: "AI Coaching Report",
    time: "30m ago",
    summary: "Report generated",
  },
  {
    id: 3,
    type: "Optimization started",
    scorecard: "SelectQuote TermLife v1",
    score: "Good Call",
    time: "1h ago",
    description: "Accuracy",
    summary: "Progress: 92%",
    data: {
      progress: 92,
      accuracy: 75,
      elapsedTime: "00:45:30",
      estimatedTimeRemaining: "00:05:00",
      numberComplete: 92,
      numberTotal: 100,
      before: {
        outerRing: [
          { category: "Positive", value: 50, fill: "var(--true)" },
          { category: "Negative", value: 50, fill: "var(--false)" },
        ],
        innerRing: [
          { category: "Positive", value: 75, fill: "var(--true)" },
          { category: "Negative", value: 25, fill: "var(--false)" },
        ],
      },
      after: {
        outerRing: [
          { category: "Positive", value: 50, fill: "var(--true)" },
          { category: "Negative", value: 50, fill: "var(--false)" },
        ],
        innerRing: [
          { category: "Positive", value: 92, fill: "var(--true)" },
          { category: "Negative", value: 8, fill: "var(--false)" },
        ],
      },
    },
  },
  {
    id: 4,
    type: "Experiment completed",
    scorecard: "SelectQuote TermLife v1",
    score: "Temperature Check",
    time: "3h ago",
    summary: "94% / 100",
    description: "Accuracy",
    data: {
      accuracy: 94,
      sensitivity: 93,
      specificity: 95,
      precision: 92,
      processedItems: 100,
      totalItems: 100,
      elapsedTime: "00:04:20",
      estimatedTimeRemaining: "00:00:00",
      confusionMatrix: {
        matrix: [
          [45, 3, 2],
          [2, 43, 2],
          [1, 2, 40],
        ],
        labels: ["Yes", "No", "NA"],
      },
    },
  },
  {
    id: 5,
    type: "Score updated",
    scorecard: "SelectQuote TermLife v1",
    score: "Assumptive Close",
    time: "1d ago",
    description: "Accuracy",
    summary: "Improved from 75% to 82%",
    data: {
      before: {
        outerRing: [
          { category: "Positive", value: 50, fill: "var(--true)" },
          { category: "Negative", value: 50, fill: "var(--false)" },
        ],
        innerRing: [
          { category: "Positive", value: 75, fill: "var(--true)" },
          { category: "Negative", value: 25, fill: "var(--false)" },
        ],
      },
      after: {
        outerRing: [
          { category: "Positive", value: 50, fill: "var(--true)" },
          { category: "Negative", value: 50, fill: "var(--false)" },
        ],
        innerRing: [
          { category: "Positive", value: 82, fill: "var(--true)" },
          { category: "Negative", value: 18, fill: "var(--false)" },
        ],
      },
    },
  },
  {
    id: 31,
    type: "Feedback queue started",
    scorecard: "CS3 Services v2",
    score: "",
    time: "5m ago",
    description: "Getting feedback",
    summary: "150 items",
    data: {
      progress: 25,
      processedItems: 37,
      totalItems: 150,
      elapsedTime: "00:10:15",
      estimatedTimeRemaining: "00:30:45",
    },
  },
  {
    id: 32,
    type: "Feedback queue completed",
    scorecard: "SelectQuote TermLife v1",
    score: "",
    time: "2h ago",
    description: "Got feedback",
    summary: "200 scores processed",
    data: {
      progress: 100,
      processedItems: 200,
      totalItems: 200,
      elapsedTime: "00:45:30",
      estimatedTimeRemaining: "00:00:00",
    },
  },
]

const chartConfig = {
  scored: { label: "Scored", color: "var(--chart-1)" },
  experiments: { label: "Experiments", color: "var(--chart-2)" },
  analysis: { label: "Analysis", color: "var(--chart-3)" },
  feedback: { label: "Feedback", color: "var(--chart-4)" },
  positive: { label: "Positive", color: "var(--true)" },
  negative: { label: "Negative", color: "var(--false)" },
}

interface BarData {
  name: string;
  scored: number;
  experiments: number;
  analysis: number;
  feedback: number;
  [key: string]: string | number;
}

function isExperimentActivity(activity: ActivityData): activity is ExperimentTask {
  return (activity.type === "Experiment started" || activity.type === "Experiment completed") 
    && activity.data !== undefined
    && 'accuracy' in activity.data 
    && 'sensitivity' in activity.data
    && 'specificity' in activity.data
    && 'precision' in activity.data
}

export default function ActivityDashboard() {
  const [selectedBar, setSelectedBar] = useState<BarData | null>(null)
  const [activities] = useState<ActivityData[]>(recentActivities)
  const [currentPage, setCurrentPage] = useState(1)
  const activitiesPerPage = 6
  const [selectedActivity, setSelectedActivity] = useState<ActivityData | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [displayedActivities, setDisplayedActivities] = useState<ActivityData[]>([])
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const { ref, inView } = useInView({
    threshold: 0,
    rootMargin: '0px 0px 400px 0px', // Increase this value to trigger earlier
  })

  const activityListRef = useRef<HTMLDivElement>(null)
  const { rightSidebarState } = useSidebar()

  const sortedActivities = useMemo(() => {
    const sorted = [...recentActivities].sort((a, b) => {
      const aMinutes = timeToMinutes(a.time);
      const bMinutes = timeToMinutes(b.time);
      return timeToMinutes(b.time) - timeToMinutes(a.time);
    });
    return sorted;
  }, []);

  useEffect(() => {
    setDisplayedActivities(sortedActivities.slice(0, 9))
    setIsInitialLoading(false)
  }, [sortedActivities])

  useEffect(() => {
    if (inView && !isLoadingMore && !isInitialLoading) {
      setIsLoadingMore(true)
      // Load more items immediately
      const currentLength = displayedActivities.length
      const more = sortedActivities.slice(currentLength, currentLength + 9)
      if (more.length > 0) {
        setDisplayedActivities(prev => [...prev, ...more])
      }
      setIsLoadingMore(false)
    }
  }, [inView, isLoadingMore, isInitialLoading, displayedActivities, sortedActivities])

  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640) // 640px is the default 'sm' breakpoint in Tailwind
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

  const totalPages = Math.ceil(sortedActivities.length / activitiesPerPage)

  const handleBarClick = (data: BarData, index: number) => {
    setSelectedBar({ ...data, index })
  }

  const renderActivityIcon = (type: string) => {
    switch (type) {
      case "Experiment completed":
      case "Experiment started":
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
      case "Experiment completed":
      case "Experiment started":
        if (isExperimentActivity(activity)) {
          return (
            <ChartContainer config={chartConfig} className="h-[120px] w-[120px] mx-auto mb-4">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Pie
                    data={[
                      { 
                        category: 'Correct', 
                        value: Math.round(activity.data.processedItems * activity.data.accuracy / 100),
                        fill: "var(--true)"
                      },
                      { 
                        category: 'Incorrect', 
                        value: activity.data.processedItems - Math.round(activity.data.processedItems * activity.data.accuracy / 100),
                        fill: "var(--false)"
                      }
                    ]}
                    dataKey="value"
                    nameKey="category"
                    outerRadius={40}
                  />
                  <Pie
                    data={[
                      { category: 'Processed', value: activity.data.processedItems, fill: "var(--true)" },
                      { category: 'Remaining', value: activity.data.totalItems - activity.data.processedItems, fill: "var(--neutral)" }
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
                      data={activity.data.before.innerRing}
                      dataKey="value"
                      nameKey="category"
                      outerRadius={30}
                      fill="var(--chart-1)"
                    />
                    <Pie
                      data={activity.data.before.outerRing}
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
                      data={activity.data.after.innerRing}
                      dataKey="value"
                      nameKey="category"
                      outerRadius={30}
                      fill="var(--chart-1)"
                    />
                    <Pie
                      data={activity.data.after.outerRing}
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

  console.log('rightSidebarState:', rightSidebarState);

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

  return (
    <div className="h-full flex">
      {/* Left side with chart and activities */}
      <div className="@container flex-1 overflow-y-auto pr-4">
        <div className="space-y-4">
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

          <Card className="shadow-none border-none mb-6 bg-card-light">
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
                      dataKey="experiments"
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
          </Card>

          <div className="grid gap-4 pb-8 grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3">
            {displayedActivities.map((activity) => (
              <div key={activity.id} className="w-full">
                {(() => {
                  switch (activity.type) {
                    case 'Experiment completed':
                    case 'Experiment started':
                      return isExperimentActivity(activity) ? (
                        <ExperimentTaskComponent
                          variant="grid"
                          task={activity}
                          onClick={() => setSelectedActivity(activity)}
                        />
                      ) : null
                    case 'Alert':
                      return (
                        <AlertTask
                          variant="grid"
                          task={activity}
                          onClick={() => setSelectedActivity(activity)}
                          iconType="warning" // Add this line
                        />
                      )
                    case 'Report':
                      return (
                        <ReportTask
                          variant="grid"
                          task={activity}
                          onClick={() => setSelectedActivity(activity)}
                        />
                      )
                    case 'Optimization started':
                      return (
                        <OptimizationTask
                          variant="grid"
                          task={{
                            ...activity,
                            scorecard: activity.description || 'Metric' // Use description or fallback to 'Metric'
                          }}
                          onClick={() => setSelectedActivity(activity)}
                        />
                      )
                    case 'Feedback queue started':
                    case 'Feedback queue completed':
                      return (
                        <FeedbackTask
                          variant="grid"
                          task={activity}
                          onClick={() => setSelectedActivity(activity)}
                        />
                      )
                    case 'Score updated':
                      return (
                        <ScoreUpdatedTask
                          variant="grid"
                          task={activity}
                          onClick={() => setSelectedActivity(activity)}
                        />
                      )
                    default:
                      return null
                  }
                })()}
              </div>
            ))}
          </div>

          <div ref={ref} className="h-12 flex items-center justify-center">
            {isLoadingMore && (
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            )}
          </div>
        </div>
      </div>

      {/* Right side detail view */}
      {selectedActivity && !isNarrowViewport && (
        <div className="w-1/3 min-w-[300px] overflow-y-auto">
          <div className="">
            <div className="" />
            {(() => {
              switch (selectedActivity.type) {
                case 'Experiment completed':
                case 'Experiment started':
                  return <ExperimentTaskComponent variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} />
                case 'Alert':
                  return <AlertTask variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} iconType="warning" />
                case 'Report':
                  return <ReportTask variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} />
                case 'Optimization started':
                  return (
                    <OptimizationTask
                      variant="detail"
                      task={{
                        ...selectedActivity,
                        scorecard: selectedActivity.description || 'Metric'
                      }}
                      controlButtons={DetailViewControlButtons}
                    />
                  )
                case 'Feedback queue started':
                case 'Feedback queue completed':
                  return <FeedbackTask variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} />
                case 'Score updated':
                  return <ScoreUpdatedTask variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} />
                default:
                  return null
              }
            })()}
          </div>
        </div>
      )}

      {/* Mobile view stays the same */}
      {selectedActivity && isNarrowViewport && (
        <div className="fixed inset-0 bg-background/80 z-50">
          <div className="container flex items-center justify-center h-full max-w-lg">
            {(() => {
              switch (selectedActivity.type) {
                case 'Experiment completed':
                case 'Experiment started':
                  return <ExperimentTaskComponent variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} />
                case 'Alert':
                  return <AlertTask variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} iconType="warning" />
                case 'Report':
                  return <ReportTask variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} />
                case 'Optimization started':
                  return (
                    <OptimizationTask
                      variant="detail"
                      task={{
                        ...selectedActivity,
                        scorecard: selectedActivity.description || 'Metric'
                      }}
                      controlButtons={DetailViewControlButtons}
                    />
                  )
                case 'Feedback queue started':
                case 'Feedback queue completed':
                  return <FeedbackTask variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} />
                case 'Score updated':
                  return <ScoreUpdatedTask variant="detail" task={selectedActivity} controlButtons={DetailViewControlButtons} />
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

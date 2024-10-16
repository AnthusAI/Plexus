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
const recentActivities = [
  {
    id: 0,
    type: "Experiment started",
    scorecard: "CS3 Services v2",
    score: "Good Call",
    time: "2m ago",
    summary: "89% / 47",
    data: {
      progress: 47,
      accuracy: 89,
      processedItems: 47,
      totalItems: 100,
      elapsedTime: "00:02:15",
      estimatedTimeRemaining: "00:03:05",
      processingRate: 23.5,
      outerRing: [
        { category: "Positive", value: 50, fill: "var(--true)" },
        { category: "Negative", value: 50, fill: "var(--false)" },
      ],
      innerRing: [
        { category: "Positive", value: 89, fill: "var(--true)" },
        { category: "Negative", value: 11, fill: "var(--false)" },
      ],
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
    type: "Analysis started",
    scorecard: "SelectQuote TermLife v1",
    score: "Good Call",
    time: "1h ago",
    summary: "Progress: 92%",
    data: {
      progress: 92,
      accuracy: 75,
      elapsedTime: "00:45:30",
      estimatedTimeRemaining: "00:05:00",
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
    data: {
      outerRing: [
        { category: "Positive", value: 50, fill: "var(--true)" },
        { category: "Negative", value: 50, fill: "var(--false)" },
      ],
      innerRing: [
        { category: "Positive", value: 94, fill: "var(--true)" },
        { category: "Negative", value: 6, fill: "var(--false)" },
      ],
    },
  },
  {
    id: 5,
    type: "Score updated",
    scorecard: "SelectQuote TermLife v1",
    score: "Assumptive Close",
    time: "1d ago",
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
    summary: "150 scores",
    data: {
      progress: 25,
      processedItems: 37,
      totalItems: 150,
      elapsedTime: "00:10:15",
      estimatedTimeRemaining: "00:30:45",
      processingRate: 3.6,
    },
  },
  {
    id: 32,
    type: "Feedback queue completed",
    scorecard: "SelectQuote TermLife v1",
    score: "",
    time: "2h ago",
    summary: "200 scores processed",
    data: {
      progress: 100,
      processedItems: 200,
      totalItems: 200,
      elapsedTime: "00:45:30",
      estimatedTimeRemaining: "00:00:00",
      processingRate: 4.4,
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

interface ActivityData {
  id: number;
  type: string;
  scorecard: string;
  score: string;
  time: string;
  summary: string;
  description?: string;
  data?: any;
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
    // Simulate initial loading
    setTimeout(() => {
      setDisplayedActivities(sortedActivities.slice(0, 9))
      setIsInitialLoading(false)
    }, 1000) // Reduced from 1500 to 1000 milliseconds
  }, [sortedActivities])

  useEffect(() => {
    if (inView && !isLoadingMore && !isInitialLoading) {
      setIsLoadingMore(true)
      setTimeout(() => {
        setIsLoadingMore(false)
        // Simulate loading more items
        const currentLength = displayedActivities.length
        const more = sortedActivities.slice(currentLength, currentLength + 9)
        if (more.length > 0) {
          setDisplayedActivities(prev => [...prev, ...more])
        }
      }, 1500) // Show loading spinner for 1.5 seconds
    }
  }, [inView, isLoadingMore, isInitialLoading, displayedActivities, sortedActivities])

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

  const totalPages = Math.ceil(sortedActivities.length / activitiesPerPage)

  const handleBarClick = (data: BarData, index: number) => {
    setSelectedBar({ ...data, index })
  }

  const renderActivityIcon = (type: string) => {
    switch (type) {
      case "Experiment completed":
      case "Experiment started":
        return <FlaskConical className="h-5 w-5" />
      case "Analysis started":
        return <Sparkles className="h-5 w-5" />
      case "Score updated":
        return <ListTodo className="h-5 w-5" />
      case "Alert":
        return <Siren className="h-5 w-5" />
      case "Report":
        return <FileText className="h-5 w-5" />
      case "Feedback queue started":
      case "Feedback queue completed":
        return <MessageCircleMore className="h-5 w-5" />
      default:
        return <Activity className="h-5 w-5" />
    }
  }

  const renderVisualization = (activity: ActivityData) => {
    if (!activity.data) return null

    switch (activity.type) {
      case "Experiment completed":
        return (
          <ChartContainer config={chartConfig} className="h-[120px] w-[120px] mx-auto mb-4">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <ChartTooltip content={<ChartTooltipContent />} />
                <Pie
                  data={activity.data.innerRing}
                  dataKey="value"
                  nameKey="category"
                  outerRadius={40}
                  fill="var(--true)"
                />
                <Pie
                  data={activity.data.outerRing}
                  dataKey="value"
                  nameKey="category"
                  innerRadius={45}
                  outerRadius={55}
                  fill="var(--chart-2)"
                />
              </PieChart>
            </ResponsiveContainer>
          </ChartContainer>
        )
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

  const handleTimeRangeChange = (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => {
    console.log("Time range changed:", range, customRange)
    // Implement the logic for handling all default time ranges and custom date ranges
  }

  const handleScorecardChange = (value: string) => {
    const newScorecardValue = value === "all" ? null : value
    setSelectedScorecard(newScorecardValue)
    setSelectedScore(null) // Always reset score selection when scorecard changes
  }

  const handleScoreChange = (value: string) => {
    setSelectedScore(value === "all" ? null : value)
  }

  return (
    <div className="space-y-4 h-full flex">
      <div className="flex-1 overflow-y-auto pr-4">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex flex-col sm:flex-row sm:items-center space-y-4 sm:space-y-0 sm:space-x-4">
              <Select onValueChange={handleScorecardChange}>
                <SelectTrigger className="w-full sm:w-[280px]">
                  <SelectValue placeholder="Scorecard" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Scorecards</SelectItem>
                  <SelectItem value="SelectQuote Term Life v1">SelectQuote Term Life v1</SelectItem>
                  <SelectItem value="CS3 Nexstar v1">CS3 Nexstar v1</SelectItem>
                  <SelectItem value="CS3 Services v2">CS3 Services v2</SelectItem>
                  <SelectItem value="CS3 Audigy">CS3 Audigy</SelectItem>
                  <SelectItem value="AW IB Sales">AW IB Sales</SelectItem>
                </SelectContent>
              </Select>
              <Select 
                onValueChange={handleScoreChange}
                disabled={!selectedScorecard}
              >
                <SelectTrigger className="w-full sm:w-[280px]">
                  <SelectValue placeholder="Score" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Scores</SelectItem>
                  {selectedScorecard && (
                    <>
                      <SelectItem value="Scoreable Call">Scoreable Call</SelectItem>
                      <SelectItem value="Call Efficiency">Call Efficiency</SelectItem>
                      <SelectItem value="Assumptive Close">Assumptive Close</SelectItem>
                      <SelectItem value="Problem Resolution">Problem Resolution</SelectItem>
                      <SelectItem value="Rapport">Rapport</SelectItem>
                      <SelectItem value="Friendly Greeting">Friendly Greeting</SelectItem>
                      <SelectItem value="Agent Offered Name">Agent Offered Name</SelectItem>
                      <SelectItem value="Temperature Check">Temperature Check</SelectItem>
                      <SelectItem value="DNC Requested">DNC Requested</SelectItem>
                      <SelectItem value="Profanity">Profanity</SelectItem>
                      <SelectItem value="Agent Offered Legal Advice">Agent Offered Legal Advice</SelectItem>
                      <SelectItem value="Agent Offered Guarantees">Agent Offered Guarantees</SelectItem>
                    </>
                  )}
                </SelectContent>
              </Select>
            </div>
            <TimeRangeSelector onTimeRangeChange={handleTimeRangeChange} />
          </div>

          <Card className="shadow-none mb-6">
            <CardContent className="p-0">
              <ChartContainer config={chartConfig} className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barChartData}>
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
                      radius={[4, 4, 0, 0]}
                    />
                    <ChartLegend content={<ChartLegendContent />} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>
            </CardContent>
          </Card>

          <div className={`grid gap-4 pb-8 ${
            rightSidebarState === 'expanded' || isNarrowViewport
              ? 'grid-cols-1'
              : isFullWidth
                ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'
                : 'grid-cols-1 md:grid-cols-2'
          }`}>
            {displayedActivities.map((activity) => (
              <Card 
                key={activity.id}
                className={`relative cursor-pointer transition-colors duration-200 ${
                  selectedActivity?.id === activity.id 
                    ? 'bg-secondary text-secondary-foreground hover:bg-secondary/90' 
                    : 'hover:bg-muted'
                }`} 
                onClick={() => setSelectedActivity(activity)}
              >
                <CardHeader className="pr-4 flex flex-col items-start">
                  <div className="flex justify-between items-start w-full">
                    <div className="flex flex-col">
                      <div className="text-lg font-bold">
                        {activity.type}
                      </div>
                      <div className={`text-xs ${
                        selectedActivity?.id === activity.id 
                          ? 'text-secondary-foreground' 
                          : 'text-muted-foreground'
                      }`}>
                        {activity.scorecard}
                      </div>
                      <div className={`text-xs ${
                        selectedActivity?.id === activity.id 
                          ? 'text-secondary-foreground' 
                          : 'text-muted-foreground'
                      }`}>
                        {activity.score || "\u00A0"}
                      </div>
                    </div>
                    <div className="flex flex-col items-end">
                      <div className="w-7 flex-shrink-0 mb-1">
                        {renderActivityIcon(activity.type)}
                      </div>
                      <div className={`text-xs ${
                        selectedActivity?.id === activity.id 
                          ? 'text-secondary-foreground' 
                          : 'text-muted-foreground'
                      }`}>
                        {activity.time}
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0 pb-4 relative min-h-[120px]">
                  <div className="flex justify-between items-start mt-4">
                    <div className="space-y-1 w-full">
                      <div className="text-lg font-bold">
                        {activity.type === "Score updated" || activity.type === "Analysis started" ? (
                          <div>
                            <div className={`text-sm ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : 'text-muted-foreground'}`}>
                              Accuracy
                            </div>
                            <div className={`flex items-center ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : ''}`}>
                              <span>{activity.data?.before?.innerRing[0]?.value ?? 0}%</span>
                              <MoveUpRight className="h-5 w-5 mx-1" />
                              <span>{activity.data?.after?.innerRing[0]?.value ?? 0}%</span>
                            </div>
                          </div>
                        ) : activity.type === "Experiment completed" || activity.type === "Experiment started" ? (
                          <div className="mb-4">
                            <div className={`text-sm ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : 'text-muted-foreground'}`}>
                              Accuracy
                            </div>
                            <div className={selectedActivity?.id === activity.id ? 'text-secondary-foreground' : ''}>{activity.summary}</div>
                          </div>
                        ) : (
                          <div className={activity.type === "Alert" ? "mb-8" : ""}>
                            {activity.description && (
                              <div className={`text-sm ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : 'text-muted-foreground'}`}>
                                {activity.description}
                              </div>
                            )}
                            <div className={selectedActivity?.id === activity.id ? 'text-secondary-foreground' : ''}>{activity.summary}</div>
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex-shrink-0 ml-4">
                      {activity.type !== "Analysis started" && 
                       activity.type !== "Experiment started" && 
                       activity.type !== "Feedback queue started" && 
                       activity.type !== "Feedback queue completed" && 
                       renderVisualization(activity)}
                    </div>
                  </div>
                  {activity.type === "Alert" && (
                    <div className="absolute bottom-4 left-0 right-0 flex justify-center">
                      <MessageCircleWarning className={`h-16 w-16 ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : 'text-destructive'}`} />
                    </div>
                  )}
                </CardContent>
                {(activity.type === "Analysis started" || 
                  activity.type === "Experiment started" || 
                  activity.type === "Feedback queue started" || 
                  activity.type === "Feedback queue completed") && 
                 activity.data && (
                  <div className="absolute bottom-0 left-0 right-0 px-6 pb-4">
                    <div className="flex justify-between text-xs mb-1">
                      <div className="font-semibold">Progress: {activity.data.progress}%</div>
                      <div>{activity.data.elapsedTime}</div>
                    </div>
                    <Progress value={activity.data.progress} className="w-full h-4" />
                    {(activity.type === "Experiment started" || 
                      activity.type === "Feedback queue started" || 
                      activity.type === "Feedback queue completed") && (
                      <div className="flex justify-between text-xs mt-1">
                        <div>{activity.data.processedItems}/{activity.data.totalItems}</div>
                        <div>
                          {activity.type === "Feedback queue completed" 
                            ? `Completed in ${activity.data.elapsedTime}`
                            : `ETA: ${activity.data.estimatedTimeRemaining}`
                          }
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            ))}
          </div>

          {/* Reduced height for bottom margin and loading indicator */}
          <div ref={ref} className="h-12 flex items-center justify-center">
            {isLoadingMore && (
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            )}
          </div>
        </div>
      </div>

      {selectedActivity && !isNarrowViewport && (
        <div className="w-1/3 min-w-[300px] pl-4 overflow-y-auto">
          <div className="space-y-4">
            <div className="" />
            <Card>
              <CardHeader className="flex flex-row items-start justify-between py-4">
                <div className="space-y-1">
                  <h2 className="text-2xl font-semibold">{selectedActivity.score}</h2>
                  <p className="text-sm text-muted-foreground">
                    {selectedActivity.time}
                  </p>
                </div>
                <Button variant="outline" size="icon" onClick={() => setSelectedActivity(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm font-medium">Type</p>
                      <p>{selectedActivity.type}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium">Scorecard</p>
                      <p>{selectedActivity.scorecard}</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Summary</p>
                    <p>{selectedActivity.summary}</p>
                  </div>
                  {selectedActivity.description && (
                    <div>
                      <p className="text-sm font-medium">Description</p>
                      <p>{selectedActivity.description}</p>
                    </div>
                  )}
                  {selectedActivity.data && (
                    <div>
                      <p className="text-sm font-medium">Visualization</p>
                      {renderVisualization(selectedActivity)}
                    </div>
                  )}
                  {(selectedActivity.type === "Analysis started" || 
                    selectedActivity.type === "Experiment started" || 
                    selectedActivity.type === "Feedback queue started" || 
                    selectedActivity.type === "Feedback queue completed") && 
                   selectedActivity.data && (
                    <div>
                      <p className="text-sm font-medium mb-2">Progress</p>
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs">
                          <div className="font-semibold">Progress: {selectedActivity.data.progress}%</div>
                          <div>{selectedActivity.data.elapsedTime}</div>
                        </div>
                        <Progress value={selectedActivity.data.progress} className="w-full h-4" />
                        {(selectedActivity.type === "Experiment started" || 
                          selectedActivity.type === "Feedback queue started" || 
                          selectedActivity.type === "Feedback queue completed") && (
                          <div className="flex justify-between text-xs">
                            <div>{selectedActivity.data.processedItems}/{selectedActivity.data.totalItems}</div>
                            <div>
                              {selectedActivity.type === "Feedback queue completed" 
                                ? `Completed in ${selectedActivity.data.elapsedTime}`
                                : `ETA: ${selectedActivity.data.estimatedTimeRemaining}`
                              }
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Mobile view for selected activity */}
      {selectedActivity && isNarrowViewport && (
        <div className="fixed inset-0 bg-background/80 z-50">
          <div className="container flex items-center justify-center h-full max-w-lg">
            <Card className="w-full max-h-[90vh] overflow-auto">
              <CardHeader className="flex flex-row items-start justify-between py-4 px-4 sm:px-6 flex-shrink-0">
                <div className="space-y-1">
                  <h2 className="text-2xl font-semibold">{selectedActivity.score}</h2>
                  <p className="text-sm text-muted-foreground">
                    {selectedActivity.time}
                  </p>
                </div>
                <div className="flex space-x-2">
                  {!isNarrowViewport && (
                    <Button variant="outline" size="icon" onClick={() => setIsFullWidth(!isFullWidth)}>
                      {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                    </Button>
                  )}
                  <Button variant="outline" size="icon" onClick={() => {
                    setSelectedActivity(null)
                    setIsFullWidth(false)
                  }}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex-grow overflow-auto px-4 sm:px-6 pb-4">
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm font-medium">Type</p>
                      <p>{selectedActivity.type}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium">Scorecard</p>
                      <p>{selectedActivity.scorecard}</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium">Summary</p>
                    <p>{selectedActivity.summary}</p>
                  </div>
                  {selectedActivity.description && (
                    <div>
                      <p className="text-sm font-medium">Description</p>
                      <p>{selectedActivity.description}</p>
                    </div>
                  )}
                  {selectedActivity.data && (
                    <div>
                      <p className="text-sm font-medium">Visualization</p>
                      {renderVisualization(selectedActivity)}
                    </div>
                  )}
                  {(selectedActivity.type === "Analysis started" || 
                    selectedActivity.type === "Experiment started" || 
                    selectedActivity.type === "Feedback queue started" || 
                    selectedActivity.type === "Feedback queue completed") && 
                   selectedActivity.data && (
                    <div>
                      <p className="text-sm font-medium mb-2">Progress</p>
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs">
                          <div className="font-semibold">Progress: {selectedActivity.data.progress}%</div>
                          <div>{selectedActivity.data.elapsedTime}</div>
                        </div>
                        <Progress value={selectedActivity.data.progress} className="w-full h-4" />
                        {(selectedActivity.type === "Experiment started" || 
                          selectedActivity.type === "Feedback queue started" || 
                          selectedActivity.type === "Feedback queue completed") && (
                          <div className="flex justify-between text-xs">
                            <div>{selectedActivity.data.processedItems}/{selectedActivity.data.totalItems}</div>
                            <div>
                              {selectedActivity.type === "Feedback queue completed" 
                                ? `Completed in ${selectedActivity.data.elapsedTime}`
                                : `ETA: ${selectedActivity.data.estimatedTimeRemaining}`
                              }
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
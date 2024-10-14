"use client"

import { useState, useMemo, useEffect, useRef, useCallback } from "react"
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { PieChart, Pie } from "recharts"
import { Progress } from "@/components/ui/progress"
import { Activity, ListTodo, FlaskConical, ArrowRight, Siren, FileText, Sparkles, ChevronLeft, ChevronRight, MoveUpRight, MessageCircleWarning, CalendarIcon, X, Square, Columns2 } from "lucide-react"
import { format } from "date-fns"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { TimeRangeSelector } from "@/components/time-range-selector"

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
  { name: "Mon", scored: 4, experiments: 3, optimizations: 2 },
  { name: "Tue", scored: 3, experiments: 4, optimizations: 3 },
  { name: "Wed", scored: 5, experiments: 2, optimizations: 4 },
  { name: "Thu", scored: 2, experiments: 5, optimizations: 1 },
  { name: "Fri", scored: 3, experiments: 3, optimizations: 3 },
  { name: "Sat", scored: 1, experiments: 2, optimizations: 2 },
  { name: "Sun", scored: 4, experiments: 1, optimizations: 5 },
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
    type: "Optimization started",
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
          { category: "Positive", value: 50, fill: "var(--false)" },
          { category: "Negative", value: 50, fill: "var(--true)" },
        ],
        innerRing: [
          { category: "Positive", value: 82, fill: "var(--true)" },
          { category: "Negative", value: 18, fill: "var(--false)" },
        ],
      },
    },
  },
]

const chartConfig = {
  scored: { label: "Scored", color: "var(--chart-1)" },
  experiments: { label: "Experiments", color: "var(--chart-2)" },
  optimizations: { label: "Optimizations", color: "var(--chart-3)" },
  positive: { label: "Positive", color: "var(--true)" },
  negative: { label: "Negative", color: "var(--false)" },
}

interface BarData {
  name: string;
  scored: number;
  experiments: number;
  optimizations: number;
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

  const activityListRef = useRef<HTMLDivElement>(null)

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

  const sortedActivities = useMemo(() => {
    const sorted = [...recentActivities].sort((a, b) => {
      const aMinutes = timeToMinutes(a.time);
      const bMinutes = timeToMinutes(b.time);
      console.log(`Comparing: ${a.time} (${aMinutes}) vs ${b.time} (${bMinutes})`);
      return timeToMinutes(b.time) - timeToMinutes(a.time);
    });
    console.log('Sorted activities:', sorted.map(a => a.time));
    return sorted;
  }, []);

  const totalPages = Math.ceil(sortedActivities.length / activitiesPerPage)

  const handleBarClick = (data: BarData, index: number) => {
    setSelectedBar({ ...data, index })
  }

  const renderActivityIcon = (type: string) => {
    switch (type) {
      case "Experiment completed":
      case "Experiment started":
        return <FlaskConical className="h-5 w-5" />
      case "Optimization started":
        return <Sparkles className="h-5 w-5" />
      case "Score updated":
        return <ListTodo className="h-5 w-5" />
      case "Alert":
        return <Siren className="h-5 w-5" />
      case "Report":
        return <FileText className="h-5 w-5" />
      default:
        return <Activity className="h-5 w-5" />
    }
  }

  const renderVisualization = (activity: ActivityData) => {
    if (!activity.data) return null

    switch (activity.type) {
      case "Experiment completed":
      case "Experiment started":
        return (
          <ChartContainer config={chartConfig} className="h-[120px] w-[120px]">
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
      case "Optimization started":
      case "Score updated":
        return (
          <div className="flex space-x-4">
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
      case "Experiment started":
        return (
          <div className="absolute bottom-4 left-6 right-7 flex flex-col space-y-1">
            <div className="flex justify-between text-xs">
              <div className="font-semibold">Progress: {activity.data.progress}%</div>
              <div>{activity.data.elapsedTime}</div>
            </div>
            <Progress value={activity.data.progress} className="w-full h-4" />
            <div className="flex justify-between text-xs">
              <div>{activity.data.processedItems}/{activity.data.totalItems}</div>
              <div>ETA: {activity.data.estimatedTimeRemaining}</div>
            </div>
          </div>
        )
      case "Optimization started":
        return (
          <div className="absolute bottom-4 left-6 right-7 flex flex-col space-y-1">
            <div className="flex justify-between text-xs">
              <div className="font-semibold">Progress: {activity.data.progress}%</div>
              <div>{activity.data.elapsedTime}</div>
            </div>
            <Progress value={activity.data.progress} className="w-full h-4" />
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

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Select>
            <SelectTrigger className="w-[180px] border border-secondary">
              <SelectValue placeholder="Scorecard" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="scorecard1">Scorecard 1</SelectItem>
              <SelectItem value="scorecard2">Scorecard 2</SelectItem>
              <SelectItem value="scorecard3">Scorecard 3</SelectItem>
            </SelectContent>
          </Select>
          <Select>
            <SelectTrigger className="w-[180px] border border-secondary">
              <SelectValue placeholder="Score" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="score1">Score 1</SelectItem>
              <SelectItem value="score2">Score 2</SelectItem>
              <SelectItem value="score3">Score 3</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <TimeRangeSelector onTimeRangeChange={handleTimeRangeChange} />
      </div>

      <div className={`flex flex-grow overflow-hidden pb-2`}>
        <div className={`flex flex-col ${isFullWidth && selectedActivity ? 'hidden' : 'flex-1'} overflow-hidden`}>
          <div className={`flex-1 overflow-auto ${selectedActivity && !isFullWidth ? 'pr-4' : ''}`}>
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
                        dataKey="optimizations"
                        stackId="a"
                        fill="var(--chart-3)"
                        onClick={handleBarClick}
                        cursor="pointer"
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartContainer>
              </CardContent>
            </Card>

            <h2 className="text-2xl font-semibold mb-4">Recent Updates</h2>
            <div className={`grid gap-4 ${selectedActivity ? 'md:grid-cols-1' : 'md:grid-cols-2'}`}>
              {sortedActivities.slice((currentPage - 1) * activitiesPerPage, currentPage * activitiesPerPage).map((activity) => (
                <Card 
                  key={activity.id}
                  data-activity-id={activity.id}
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
                  <CardContent className="pt-0 pb-20 relative min-h-[200px]">
                    <div className="flex justify-between items-start mt-4">
                      <div className="space-y-1 w-full">
                        <div className="text-lg font-bold">
                          {activity.type === "Score updated" || activity.type === "Optimization started" ? (
                            <div>
                              <div className={`flex items-center ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : ''}`}>
                                <span>{activity.data?.before?.innerRing[0]?.value ?? 0}%</span>
                                <MoveUpRight className="h-5 w-5 mx-1" />
                                <span>{activity.data?.after?.innerRing[0]?.value ?? 0}%</span>
                              </div>
                              <div className={`text-sm ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : 'text-muted-foreground'}`}>
                                Accuracy
                              </div>
                            </div>
                          ) : activity.type === "Experiment completed" || activity.type === "Experiment started" ? (
                            <div>
                              <div className={selectedActivity?.id === activity.id ? 'text-secondary-foreground' : ''}>{activity.summary}</div>
                              <div className={`text-sm ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : 'text-muted-foreground'}`}>
                                Accuracy
                              </div>
                            </div>
                          ) : (
                            <div>
                              <div className={selectedActivity?.id === activity.id ? 'text-secondary-foreground' : ''}>{activity.summary}</div>
                              {activity.description && (
                                <div className={`text-sm ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : 'text-muted-foreground'}`}>
                                  {activity.description}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex-shrink-0 ml-4">
                        {renderVisualization(activity)}
                      </div>
                    </div>
                    {activity.type === "Alert" && (
                      <div className="absolute bottom-4 left-0 right-0 flex justify-center">
                        <MessageCircleWarning className={`h-16 w-16 ${selectedActivity?.id === activity.id ? 'text-secondary-foreground' : 'text-destructive'}`} />
                      </div>
                    )}
                    {(activity.type === "Optimization started" || activity.type === "Experiment started") && activity.data && (
                      <div className="absolute bottom-4 left-6 right-7 flex flex-col space-y-1">
                        <div className="flex justify-between text-xs">
                          <div className="font-semibold">Progress: {activity.data.progress}%</div>
                          <div>{activity.data.elapsedTime}</div>
                        </div>
                        <Progress value={activity.data.progress} className="w-full h-4" />
                        {activity.type === "Experiment started" && (
                          <div className="flex justify-between text-xs">
                            <div>{activity.data.processedItems}/{activity.data.totalItems}</div>
                            <div>ETA: {activity.data.estimatedTimeRemaining}</div>
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
            <div className="flex justify-between items-center mt-4">
              <Button
                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                disabled={currentPage === 1}
                variant="outline"
              >
                <ChevronLeft className="h-4 w-4 mr-2" />
                Previous
              </Button>
              <span>Page {currentPage} of {totalPages}</span>
              <Button
                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                disabled={currentPage === totalPages}
                variant="outline"
              >
                Next
                <ChevronRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </div>
        </div>

        {selectedActivity && (
          <div className={`flex-shrink-0 ${isFullWidth ? 'w-full' : 'w-1/2'} overflow-hidden flex flex-col`}>
            <Card className="rounded-none sm:rounded-lg flex flex-col h-full">
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
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
"use client"

import { useState, useMemo } from "react"
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { PieChart, Pie } from "recharts"
import { Progress } from "@/components/ui/progress"
import { Activity, ListTodo, FlaskConical, ArrowRight, Siren, FileText, Sparkles, ChevronLeft, ChevronRight, MoveUpRight, MessageCircleWarning, CalendarIcon } from "lucide-react"
import { format } from "date-fns"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

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

  // Add this new state for the selected time range
  const [selectedTimeRange, setSelectedTimeRange] = useState("last_week")
  const [customDateRange, setCustomDateRange] = useState<{
    from: Date | undefined;
    to: Date | undefined;
  }>({
    from: undefined,
    to: undefined,
  })

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
        return <Siren className="h-5 w-5 text-destructive" />
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
      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Activity</h1>
        <p className="text-muted-foreground">
          Recent experiments run, optimizations started or completed, and other activity.
        </p>
      </div>

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
        <div className="flex items-center space-x-4">
          <Select
            value={selectedTimeRange}
            onValueChange={setSelectedTimeRange}
          >
            <SelectTrigger className="w-[200px] border border-secondary">
              <SelectValue placeholder="Time Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="last_hour">Last hour</SelectItem>
              <SelectItem value="last_3_hours">Last 3 hours</SelectItem>
              <SelectItem value="last_12_hours">Last 12 hours</SelectItem>
              <SelectItem value="last_24_hours">Last 24 hours</SelectItem>
              <SelectItem value="last_3_days">Last 3 days</SelectItem>
              <SelectItem value="last_week">Last week</SelectItem>
              <SelectItem value="custom">Custom</SelectItem>
            </SelectContent>
          </Select>
          {selectedTimeRange === "custom" && (
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant={"outline"}
                  className={`w-[300px] justify-start text-left font-normal ${
                    !customDateRange.from && "text-muted-foreground"
                  }`}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {customDateRange.from ? (
                    customDateRange.to ? (
                      <>
                        {format(customDateRange.from, "LLL dd, y")} -{" "}
                        {format(customDateRange.to, "LLL dd, y")}
                      </>
                    ) : (
                      format(customDateRange.from, "LLL dd, y")
                    )
                  ) : (
                    <span>Pick a date range</span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  initialFocus
                  mode="range"
                  defaultMonth={customDateRange.from}
                  selected={customDateRange}
                  onSelect={setCustomDateRange}
                  numberOfMonths={2}
                />
              </PopoverContent>
            </Popover>
          )}
        </div>
      </div>

      <Card className="shadow-none">
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

      <div>
        <h2 className="text-2xl font-semibold mb-4">Recent Updates</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {sortedActivities.slice((currentPage - 1) * activitiesPerPage, currentPage * activitiesPerPage).map((activity) => (
            <Card key={activity.id} className="relative">
              <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2 pl-10">
                <div className="flex items-start">
                  <div className="w-7 flex-shrink-0 -ml-7">
                    {renderActivityIcon(activity.type)}
                  </div>
                  <div>
                    <CardTitle className="text-sm font-medium">
                      {activity.type}
                    </CardTitle>
                    <div className="text-xs text-muted-foreground">
                      {activity.time}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {activity.scorecard}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {activity.score || "\u00A0"}
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2 text-xs"
                  onClick={() => console.log(`View details for ${activity.id}`)}
                >
                  Details
                  <ArrowRight className="ml-1 h-3 w-3" />
                </Button>
              </CardHeader>
              <CardContent className="pl-10">
                <div className="flex justify-between items-start">
                  <div className="space-y-1 w-full">
                    <div className="text-lg font-bold mt-2">
                      {activity.type === "Score updated" || activity.type === "Optimization started" ? (
                        <div>
                          <div className="flex items-center">
                            <span>{activity.data?.before?.innerRing[0]?.value ?? 0}%</span>
                            <MoveUpRight className="h-5 w-5 mx-1" />
                            <span>{activity.data?.after?.innerRing[0]?.value ?? 0}%</span>
                          </div>
                          <div className="text-sm text-muted-foreground">
                            Accuracy
                          </div>
                        </div>
                      ) : activity.type === "Experiment completed" || activity.type === "Experiment started" ? (
                        <div>
                          <div>{activity.summary}</div>
                          <div className="text-sm text-muted-foreground">
                            Accuracy
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div>{activity.summary}</div>
                          {activity.description && (
                            <div className="text-sm text-muted-foreground">
                              {activity.description}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    {activity.type === "Alert" && (
                      <div className="flex justify-center mt-4">
                        <MessageCircleWarning className="h-16 w-16 text-red-500" />
                      </div>
                    )}
                  </div>
                  <div className="flex-shrink-0 ml-4">
                    {renderVisualization(activity)}
                  </div>
                </div>
                {(activity.type === "Optimization started" || activity.type === "Experiment started") && activity.data && (
                  <div className="mt-4">
                    <div className="text-sm font-medium mb-1">Progress: {activity.data.progress}%</div>
                    <div className="relative">
                      <Progress value={activity.data.progress} className="w-full h-2 absolute" />
                    </div>
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
  )
}
"use client"

import { useState } from "react"
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

// Mock data for the chart
const data = [
  { name: "Mon", scored: 4, experiments: 3, optimizations: 2 },
  { name: "Tue", scored: 3, experiments: 4, optimizations: 3 },
  { name: "Wed", scored: 5, experiments: 2, optimizations: 4 },
  { name: "Thu", scored: 2, experiments: 5, optimizations: 1 },
  { name: "Fri", scored: 3, experiments: 3, optimizations: 3 },
  { name: "Sat", scored: 1, experiments: 2, optimizations: 2 },
  { name: "Sun", scored: 4, experiments: 1, optimizations: 5 },
]

// Mock data for the detail view and recent updates
const updateData = [
  { id: 1, title: "Experiment A completed", description: "Experiment A has been successfully completed with positive results." },
  { id: 2, title: "New optimization started", description: "A new optimization process has been initiated for Project X." },
  { id: 3, title: "Score update", description: "The score for Product Y has been updated based on recent performance metrics." },
  { id: 4, title: "Experiment B launched", description: "A new experiment, Experiment B, has been launched to test hypothesis Z." },
  { id: 5, title: "Optimization milestone reached", description: "The ongoing optimization for Service W has reached a significant milestone." },
]

interface BarData {
  name: string;
  scored: number;
  experiments: number;
  optimizations: number;
  [key: string]: string | number;
}

export default function ActivityDashboard() {
  const [selectedBar, setSelectedBar] = useState<BarData | null>(null)

  const handleBarClick = (data: BarData, index: number) => {
    setSelectedBar({ ...data, index })
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Activity</h1>
          <p className="text-muted-foreground">
            Recent items scored, experiments run, optimizations started or completed, and other activity.
          </p>
        </div>
        <div className="flex space-x-2">
          {["1h", "3h", "12h", "1d", "3d", "1w"].map((range) => (
            <Button key={range} variant="outline" size="sm">
              {range}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex space-x-4">
        <Select>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select Scorecard" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="scorecard1">Scorecard 1</SelectItem>
            <SelectItem value="scorecard2">Scorecard 2</SelectItem>
            <SelectItem value="scorecard3">Scorecard 3</SelectItem>
          </SelectContent>
        </Select>
        <Select>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select Score" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="score1">Score 1</SelectItem>
            <SelectItem value="score2">Score 2</SelectItem>
            <SelectItem value="score3">Score 3</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card className="bg-[hsl(var(--light-blue-bg))]">
        <CardHeader>
          <CardTitle>Activity Overview</CardTitle>
          <CardDescription>Stacked bar chart showing activity breakdown</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <ChartContainer
            config={{
              scored: {
                label: "Scored",
                color: "hsl(var(--chart-primary))",
              },
              experiments: {
                label: "Experiments",
                color: "hsl(var(--chart-secondary))",
              },
              optimizations: {
                label: "Optimizations",
                color: "hsl(var(--chart-accent))",
              },
            }}
            className="h-[300px] w-full"
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data}>
                <XAxis dataKey="name" />
                <YAxis />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar
                  dataKey="scored"
                  stackId="a"
                  fill="hsl(var(--chart-primary))"
                  onClick={handleBarClick}
                  cursor="pointer"
                />
                <Bar
                  dataKey="experiments"
                  stackId="a"
                  fill="hsl(var(--chart-secondary))"
                  onClick={handleBarClick}
                  cursor="pointer"
                />
                <Bar
                  dataKey="optimizations"
                  stackId="a"
                  fill="hsl(var(--chart-accent))"
                  onClick={handleBarClick}
                  cursor="pointer"
                />
              </BarChart>
            </ResponsiveContainer>
          </ChartContainer>
        </CardContent>
      </Card>

      <div>
        <h2 className="text-2xl font-semibold mb-4">
          {selectedBar ? `Updates for ${selectedBar.name}` : "Recent Updates"}
        </h2>
        {selectedBar ? (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <h3 className="font-semibold">Scored</h3>
                <p>{selectedBar.scored}</p>
              </div>
              <div>
                <h3 className="font-semibold">Experiments</h3>
                <p>{selectedBar.experiments}</p>
              </div>
              <div>
                <h3 className="font-semibold">Optimizations</h3>
                <p>{selectedBar.optimizations}</p>
              </div>
            </div>
            {updateData.slice(0, 3).map((item) => (
              <Card key={item.id}>
                <CardHeader>
                  <CardTitle className="text-lg">{item.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p>{item.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {updateData.map((item) => (
              <Card key={item.id}>
                <CardHeader>
                  <CardTitle className="text-lg">{item.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p>{item.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
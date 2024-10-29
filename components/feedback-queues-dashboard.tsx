"use client"

import React from "react"
import { useState, useMemo } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { formatDistanceToNow, parseISO } from "date-fns"
import { useRouter } from 'next/navigation'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

// Get the current date and time
const now = new Date();

// Function to create a date relative to now
const relativeDate = (days: number, hours: number, minutes: number) => {
  const date = new Date(now);
  date.setDate(date.getDate() - days);
  date.setHours(date.getHours() - hours, date.getMinutes() - minutes);
  return date.toISOString();
};

// Define score counts for each scorecard
const scorecardScoreCounts = {
  "CS3 Services v2": 1,
  "CS3 Audigy": 4,
  "AW IB Sales": 1,
  "CS3 Nexstar v1": 29,
  "SelectQuote Term Life v1": 42,
};

const feedbackQueues = [
  { id: 1, name: "CS3 Services v2", scores: 1, items: 150, date: relativeDate(0, 1, 0), started: relativeDate(0, 2, 0), progress: 75 },
  { id: 2, name: "CS3 Audigy", scores: 4, items: 80, date: relativeDate(0, 2, 0), started: relativeDate(0, 3, 0), progress: 60 },
  { id: 3, name: "AW IB Sales", scores: 1, items: 200, date: relativeDate(0, 3, 0), started: relativeDate(0, 4, 0), progress: 90 },
  { id: 4, name: "CS3 Nexstar v1", scores: 29, items: 100, date: relativeDate(0, 4, 0), started: relativeDate(0, 5, 0), progress: 40 },
  { id: 5, name: "SelectQuote Term Life v1", scores: 42, items: 120, date: relativeDate(0, 5, 0), started: relativeDate(0, 6, 0), progress: 100 },
  { id: 6, name: "CS3 Services v2", scores: 1, items: 180, date: relativeDate(1, 0, 0), started: relativeDate(1, 1, 0), progress: 80 },
  { id: 7, name: "AW IB Sales", scores: 1, items: 90, date: relativeDate(1, 6, 0), started: relativeDate(1, 7, 0), progress: 30 },
  { id: 8, name: "CS3 Audigy", scores: 4, items: 110, date: relativeDate(2, 0, 0), started: relativeDate(2, 1, 0), progress: 70 },
  { id: 9, name: "SelectQuote Term Life v1", scores: 42, items: 130, date: relativeDate(2, 12, 0), started: relativeDate(2, 13, 0), progress: 100 },
  { id: 10, name: "CS3 Nexstar v1", scores: 29, items: 160, date: relativeDate(3, 0, 0), started: relativeDate(3, 1, 0), progress: 85 },
];

export default function FeedbackQueuesDashboard() {
  const router = useRouter();
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null);

  const getRelativeTime = (dateString: string) => {
    const date = parseISO(dateString)
    return formatDistanceToNow(date, { addSuffix: true })
  }

  const renderProgressBar = (progress: number) => {
    return (
      <div className="relative w-full h-6 bg-neutral rounded-full">
        <div
          className="absolute top-0 left-0 h-full bg-primary flex items-center pl-2 text-xs text-primary-foreground font-medium rounded-full"
          style={{ width: `${progress}%` }}
        >
          {progress}%
        </div>
      </div>
    )
  }

  const handleRowClick = (queueId: number) => {
    router.push(`/feedback?queue=${queueId}`);
  }

  const filteredQueues = useMemo(() => {
    if (!selectedScorecard) return feedbackQueues;
    return feedbackQueues.filter(queue => queue.name === selectedScorecard);
  }, [selectedScorecard]);

  const uniqueScorecards = useMemo(() => {
    return Object.keys(scorecardScoreCounts);
  }, []);

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex items-center space-x-4">
        <Select onValueChange={(value) => setSelectedScorecard(value === "all" ? null : value)}>
          <SelectTrigger className="w-[280px] border border-secondary">
            <SelectValue placeholder="Scorecard" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Scorecards</SelectItem>
            {uniqueScorecards.map((scorecard) => (
              <SelectItem key={scorecard} value={scorecard}>{scorecard}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex-grow flex flex-col overflow-hidden pb-2">
        <div className="@container flex-1 overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[25%]">Feedback Queue</TableHead>
                <TableHead className="w-[15%] @[630px]:table-cell hidden">Started</TableHead>
                <TableHead className="w-[15%] @[630px]:table-cell hidden">Last Updated</TableHead>
                <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Scores</TableHead>
                <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">Items</TableHead>
                <TableHead className="w-[25%] @[630px]:table-cell hidden">Progress</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredQueues.map((queue) => (
                <TableRow 
                  key={queue.id} 
                  onClick={() => handleRowClick(queue.id)}
                  className="cursor-pointer hover:bg-muted"
                >
                  <TableCell className="font-medium">
                    <div>
                      {/* Narrow variant - visible below 630px */}
                      <div className="block @[630px]:hidden">
                        <div className="flex justify-between items-start mb-2">
                          <div className="font-semibold">{queue.name}</div>
                          <div className="text-sm text-muted-foreground text-right">
                            {queue.scores} scores<br />
                            {queue.items} items
                          </div>
                        </div>
                        <div className="text-sm text-muted-foreground mb-2">
                          Started {getRelativeTime(queue.started)}
                        </div>
                        {renderProgressBar(queue.progress)}
                      </div>
                      {/* Wide variant - visible at 630px and above */}
                      <div className="hidden @[630px]:block">
                        {queue.name}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden @[630px]:table-cell">{getRelativeTime(queue.started)}</TableCell>
                  <TableCell className="hidden @[630px]:table-cell">{getRelativeTime(queue.date)}</TableCell>
                  <TableCell className="hidden @[630px]:table-cell text-right">{queue.scores}</TableCell>
                  <TableCell className="hidden @[630px]:table-cell text-right">{queue.items}</TableCell>
                  <TableCell className="hidden @[630px]:table-cell">{renderProgressBar(queue.progress)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  )
}

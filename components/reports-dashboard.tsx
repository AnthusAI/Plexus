"use client"

import React, { useState, useMemo } from "react"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { Eye, X, Columns2, Square, Pencil } from "lucide-react"
import { format, formatDistanceToNow, subDays, subHours, subMinutes } from "date-fns"

interface Report {
  id: string
  name: string
  scorecard: string
  description: string
  lastRun: Date
  runs: Array<{ id: string; timestamp: Date }>
}

export default function ReportsDashboard() {
  const now = useMemo(() => new Date(), [])

  const generateRuns = (count: number, lastRun: Date): Array<{ id: string; timestamp: Date }> => {
    return Array.from({ length: count }, (_, i) => ({
      id: `run${i + 1}`,
      timestamp: subDays(lastRun, Math.floor(i / 3)) // More frequent runs
    }))
  }

  const initialReports: Report[] = useMemo(() => [
    {
      id: "1",
      name: "AI Coaching Report - Agents, Monthly",
      scorecard: "SelectQuote Term Life v1",
      description: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
      lastRun: subHours(now, 2),
      runs: generateRuns(60, subHours(now, 2))
    },
    {
      id: "2",
      name: "AI Coaching Report - Managers, Weekly",
      scorecard: "SelectQuote Term Life v1",
      description: "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
      lastRun: subDays(now, 2),
      runs: generateRuns(60, subDays(now, 2))
    },
    {
      id: "3",
      name: "Compliance Report - Weekly",
      scorecard: "CS3 Audigy TPA",
      description: "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.",
      lastRun: subHours(now, 12),
      runs: generateRuns(60, subHours(now, 12))
    },
    {
      id: "4",
      name: "Sales Report - Monthly",
      scorecard: "CS3 Services v2",
      description: "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
      lastRun: subDays(now, 1),
      runs: generateRuns(60, subDays(now, 1))
    },
    {
      id: "5",
      name: "AI Coaching Report - Agents, Monthly",
      scorecard: "Prime Edu",
      description: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
      lastRun: subMinutes(now, 30),
      runs: generateRuns(60, subMinutes(now, 30))
    },
  ], [now])

  const [reports] = useState<Report[]>(initialReports)
  const [selectedReport, setSelectedReport] = useState<Report | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)

  const renderReportsTable = () => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[60%]">Report Name</TableHead>
          <TableHead className="w-[30%]">Last Run</TableHead>
          <TableHead className="w-[10%] text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {reports.map((report) => (
          <TableRow 
            key={report.id} 
            className="cursor-pointer transition-colors duration-200 hover:bg-muted"
            onClick={() => setSelectedReport(report)}
          >
            <TableCell>
              <div className="font-medium">{report.name}</div>
              <div className="text-sm text-muted-foreground">{report.scorecard}</div>
            </TableCell>
            <TableCell>
              {formatDistanceToNow(report.lastRun, { addSuffix: true })}
            </TableCell>
            <TableCell className="text-right">
              <Button 
                variant="ghost" 
                size="icon"
                onClick={(e) => { e.stopPropagation(); setSelectedReport(report); }}
                className="h-8 w-8"
              >
                <Eye className="h-4 w-4" />
              </Button>
              <Button 
                variant="ghost" 
                size="icon"
                onClick={(e) => { e.stopPropagation(); console.log("Edit report", report.id); }}
                className="h-8 w-8 ml-2"
              >
                <Pencil className="h-4 w-4" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )

  const renderSelectedReport = () => {
    if (!selectedReport) return null

    return (
      <Card className="rounded-none sm:rounded-lg h-full flex flex-col">
        <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between py-4 px-4 sm:px-6 space-y-0">
          <div className="flex-grow">
            <h2 className="text-xl font-semibold">{selectedReport.name}</h2>
            <p className="text-sm text-muted-foreground">{selectedReport.scorecard}</p>
          </div>
          <div className="flex ml-2">
            <Button variant="outline" size="icon" onClick={() => console.log("Edit report", selectedReport.id)}>
              <Pencil className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={() => setIsFullWidth(!isFullWidth)} className="ml-2">
              {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
            </Button>
            <Button variant="outline" size="icon" onClick={() => setSelectedReport(null)} className="ml-2">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex-grow overflow-auto px-4 sm:px-6 pb-6">
          <p className="text-muted-foreground mb-4">{selectedReport.description}</p>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold">Runs</h3>
          </div>
          <div className="max-h-[400px] overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {selectedReport.runs.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell>{format(run.timestamp, "PPpp")}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Eye className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex-grow overflow-hidden pb-2">
        <div className="flex space-x-6 h-full overflow-hidden">
          <div className={`${isFullWidth && selectedReport ? 'hidden' : 'flex-1'} overflow-auto`}>
            {renderReportsTable()}
          </div>
          {selectedReport && (
            <div className={`${isFullWidth ? 'flex-1' : 'flex-1'} overflow-hidden`}>
              {renderSelectedReport()}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
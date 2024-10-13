"use client"

import { useState, useMemo, useEffect } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, Settings } from "lucide-react"
import { format, formatDistanceToNow, parseISO } from "date-fns"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

// Get the current date and time
const now = new Date();

// Function to create a date relative to now
const relativeDate = (days: number, hours: number, minutes: number) => {
  const date = new Date(now);
  date.setDate(date.getDate() - days);
  date.setHours(date.getHours() - hours, date.getMinutes() - minutes);
  return date.toISOString();
};

const alerts = [
  { id: 1, message: "Inappropriate language detected", source: "CS3 Services v2", date: relativeDate(0, 0, 5), status: "new", severity: "high" },
  { id: 2, message: "DNC request detected", source: "CS3 Audigy", date: relativeDate(0, 0, 10), status: "new", severity: "medium" },
  { id: 3, message: "Agent gave legal advice", source: "AW IB Sales", date: relativeDate(0, 0, 15), status: "new", severity: "high" },
  { id: 4, message: "Agent gave guarantee", source: "SelectQuote Term Life v1", date: relativeDate(0, 1, 0), status: "activities...", severity: "medium" },
  { id: 5, message: "Inappropriate language detected", source: "CS3 Nexstar v1", date: relativeDate(0, 2, 0), status: "activities...", severity: "high" },
  { id: 6, message: "DNC request detected", source: "CS3 Services v2", date: relativeDate(0, 3, 0), status: "activities...", severity: "medium" },
  { id: 7, message: "Agent gave legal advice", source: "AW IB Sales", date: relativeDate(0, 4, 0), status: "activities...", severity: "high" },
  { id: 8, message: "No new data in the last 24 hours", source: "System", date: relativeDate(1, 0, 0), status: "resolved", severity: "low" },
  { id: 9, message: "Exception from Plexus processing: NullPointerException at line 237", source: "System", date: relativeDate(2, 0, 0), status: "resolved", severity: "critical" },
  { id: 10, message: "Compliance training overdue for multiple agents", source: "CS3 Audigy", date: relativeDate(3, 0, 0), status: "resolved", severity: "medium" },
  { id: 11, message: "Unusual spike in refund requests", source: "CS3 Nexstar v1", date: relativeDate(4, 0, 0), status: "resolved", severity: "high" },
  { id: 12, message: "Agent provided incorrect product information", source: "SelectQuote Term Life v1", date: relativeDate(5, 0, 0), status: "resolved", severity: "medium" },
  { id: 13, message: "Customer reported missing callback", source: "CS3 Services v2", date: relativeDate(6, 0, 0), status: "resolved", severity: "low" },
  { id: 14, message: "Potential data breach detected", source: "System", date: relativeDate(7, 0, 0), status: "resolved", severity: "critical" },
  { id: 15, message: "Agent used unauthorized script", source: "AW IB Sales", date: relativeDate(8, 0, 0), status: "resolved", severity: "high" },
  { id: 16, message: "Customer satisfaction score dropped below threshold", source: "CS3 Audigy", date: relativeDate(9, 0, 0), status: "resolved", severity: "medium" },
  { id: 17, message: "System maintenance required", source: "System", date: relativeDate(10, 0, 0), status: "resolved", severity: "low" },
  { id: 18, message: "Agent exceeded maximum call duration", source: "CS3 Nexstar v1", date: relativeDate(11, 0, 0), status: "resolved", severity: "medium" },
  { id: 19, message: "Potential fraud attempt detected", source: "SelectQuote Term Life v1", date: relativeDate(12, 0, 0), status: "resolved", severity: "high" },
  { id: 20, message: "API rate limit exceeded", source: "System", date: relativeDate(13, 0, 0), status: "resolved", severity: "medium" },
  { id: 21, message: "Agent failed to verify customer identity", source: "CS3 Services v2", date: relativeDate(14, 0, 0), status: "resolved", severity: "high" },
  { id: 22, message: "Unusual pattern in call transfers", source: "AW IB Sales", date: relativeDate(15, 0, 0), status: "resolved", severity: "medium" },
  { id: 23, message: "Customer reported incorrect billing", source: "CS3 Audigy", date: relativeDate(16, 0, 0), status: "resolved", severity: "high" },
  { id: 24, message: "System backup failure", source: "System", date: relativeDate(17, 0, 0), status: "resolved", severity: "critical" },
  { id: 25, message: "Agent used discriminatory language", source: "CS3 Nexstar v1", date: relativeDate(18, 0, 0), status: "resolved", severity: "critical" },
  { id: 26, message: "Unusual increase in call abandonment rate", source: "SelectQuote Term Life v1", date: relativeDate(19, 0, 0), status: "resolved", severity: "medium" },
  { id: 27, message: "Customer data update failed", source: "System", date: relativeDate(20, 0, 0), status: "resolved", severity: "high" },
  { id: 28, message: "Agent failed to follow up on customer request", source: "CS3 Services v2", date: relativeDate(21, 0, 0), status: "resolved", severity: "medium" },
  { id: 29, message: "Potential security vulnerability detected", source: "System", date: relativeDate(22, 0, 0), status: "resolved", severity: "critical" },
  { id: 30, message: "Customer reported missing order", source: "AW IB Sales", date: relativeDate(23, 0, 0), status: "resolved", severity: "high" },
];

// Sort alerts by date, newest first
alerts.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

// Sample metadata for all alerts
const sampleMetadata = [
  { key: "Alert ID", value: "ALT-12345" },
  { key: "Triggered By", value: "Scorecard Evaluation" },
  { key: "Associated Item", value: "ITEM-67890" },
];

export default function AlertsDashboard() {
  const [selectedAlert, setSelectedAlert] = useState<number | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [selectedSource, setSelectedSource] = useState<string | null>(null)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)

  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }

    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)

    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  const filteredAlerts = useMemo(() => {
    return alerts.filter(alert => 
      !selectedSource || alert.source === selectedSource
    )
  }, [selectedSource])

  const getRelativeTime = (dateString: string) => {
    const date = parseISO(dateString)
    return formatDistanceToNow(date, { addSuffix: true })
  }

  const handleAlertClick = (alertId: number) => {
    setSelectedAlert(alertId)
    if (isNarrowViewport) {
      setIsFullWidth(true)
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'low': return 'bg-green-500'
      case 'medium': return 'bg-yellow-500'
      case 'high': return 'bg-orange-500'
      case 'critical': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  return (
    <div className="space-y-6">

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0 sm:space-x-4">
        <div className="flex flex-col sm:flex-row sm:items-center space-y-4 sm:space-y-0 sm:space-x-4">
          <Select onValueChange={(value) => setSelectedSource(value === "all" ? null : value)}>
            <SelectTrigger className="w-full sm:w-[280px] border border-secondary">
              <SelectValue placeholder="Source" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Sources</SelectItem>
              <SelectItem value="CS3 Services v2">CS3 Services v2</SelectItem>
              <SelectItem value="CS3 Audigy">CS3 Audigy</SelectItem>
              <SelectItem value="AW IB Sales">AW IB Sales</SelectItem>
              <SelectItem value="SelectQuote Term Life v1">SelectQuote Term Life v1</SelectItem>
              <SelectItem value="CS3 Nexstar v1">CS3 Nexstar v1</SelectItem>
              <SelectItem value="System">System</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" className="flex items-center gap-2">
          <Settings className="h-4 w-4" />
          Manage Alerts
        </Button>
      </div>

      <div className={`flex ${isNarrowViewport || isFullWidth ? 'flex-col' : 'space-x-6'}`}>
        <div className={`${isFullWidth && selectedAlert ? 'hidden' : 'flex-1'}`}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[60%]">Alert</TableHead>
                <TableHead className="w-[20%]">Severity</TableHead>
                <TableHead className="w-[20%] text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAlerts.map((alert) => (
                <TableRow key={alert.id} onClick={() => handleAlertClick(alert.id)} className="cursor-pointer">
                  <TableCell className="font-medium">
                    <div className="space-y-1">
                      <div className="font-semibold">{alert.message}</div>
                      <div className="text-sm text-muted-foreground">{alert.source}</div>
                      <div className="text-sm text-muted-foreground">{getRelativeTime(alert.date)}</div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${getSeverityColor(alert.severity)}`} />
                      {alert.severity}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge 
                      variant={alert.status === 'new' ? 'default' : alert.status === 'activities...' ? 'secondary' : 'outline'}
                      className="w-24 justify-center"
                    >
                      {alert.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {selectedAlert && (
          <div className={`${isFullWidth ? 'w-full' : 'w-1/2'} ${isNarrowViewport || isFullWidth ? 'mx-0' : ''}`}>
            <Card className={`rounded-none sm:rounded-lg flex flex-col h-[calc(100vh-8rem)]`}>
              <CardHeader className="flex flex-row items-center justify-between py-4 px-4 sm:px-6">
                <div className="space-y-1">
                  <h3 className="text-2xl font-semibold">{alerts.find(alert => alert.id === selectedAlert)?.message}</h3>
                  <p className="text-sm text-muted-foreground">
                    {alerts.find(alert => alert.id === selectedAlert)?.source} • {getRelativeTime(alerts.find(alert => alert.id === selectedAlert)?.date || '')}
                  </p>
                </div>
                <div className="flex space-x-2">
                  {!isNarrowViewport && (
                    <Button variant="outline" size="icon" onClick={() => setIsFullWidth(!isFullWidth)}>
                      {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                    </Button>
                  )}
                  <Button variant="outline" size="icon" onClick={() => {
                    setSelectedAlert(null)
                    setIsFullWidth(false)
                  }}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex-grow overflow-auto px-4 sm:px-6">
                {selectedAlert && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm font-medium">Severity</p>
                        <div className="flex items-center gap-2">
                          <div className={`w-3 h-3 rounded-full ${getSeverityColor(alerts.find(alert => alert.id === selectedAlert)?.severity || '')}`} />
                          {alerts.find(alert => alert.id === selectedAlert)?.severity}
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">Status</p>
                        <Badge 
                          variant={alerts.find(alert => alert.id === selectedAlert)?.status === 'new' ? 'default' : alerts.find(alert => alert.id === selectedAlert)?.status === 'activities...' ? 'secondary' : 'outline'}
                        >
                          {alerts.find(alert => alert.id === selectedAlert)?.status}
                        </Badge>
                      </div>
                    </div>
                    <div>
                      <h4 className="text-md font-semibold">Metadata</h4>
                      <hr className="my-2 border-t border-gray-200" />
                      <Table>
                        <TableBody>
                          {sampleMetadata.map((meta, index) => (
                            <TableRow key={index}>
                              <TableCell className="font-medium pl-0">{meta.key}</TableCell>
                              <TableCell className="text-right pr-0">{meta.value}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                    <div>
                      <h4 className="text-md font-semibold">Description</h4>
                      <hr className="my-2 border-t border-gray-200" />
                      <p className="text-sm">
                        This alert was triggered based on the scoring results of the associated item. 
                        The system detected a potential issue that requires attention or investigation.
                        Please review the details and take appropriate action as needed.
                      </p>
                    </div>
                    <div>
                      <h4 className="text-md font-semibold">Activities</h4>
                      <hr className="my-2 border-t border-gray-200" />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
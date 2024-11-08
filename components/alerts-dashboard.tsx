"use client"

import { useState, useMemo, useEffect } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, Settings } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatTimeAgo } from '@/utils/format-time'

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
  { id: 4, message: "Agent gave guarantee", source: "SelectQuote Term Life v1", date: relativeDate(0, 1, 0), status: "actions...", severity: "medium" },
  { id: 5, message: "Inappropriate language detected", source: "CS3 Nexstar v1", date: relativeDate(0, 2, 0), status: "actions...", severity: "high" },
  { id: 6, message: "DNC request detected", source: "CS3 Services v2", date: relativeDate(0, 3, 0), status: "actions...", severity: "medium" },
  { id: 7, message: "Agent gave legal advice", source: "AW IB Sales", date: relativeDate(0, 4, 0), status: "actions...", severity: "high" },
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

  const getBadgeVariant = (status: string) => {
    switch (status) {
      case 'new':
        return 'bg-neutral text-primary-foreground h-6';
      case 'actions...':
        return 'bg-secondary text-secondary-foreground h-6';
      case 'resolved':
        return 'bg-true text-primary-foreground h-6';
      default:
        return 'bg-muted text-muted-foreground h-6';
    }
  };

  return (
    <div className="space-y-4 h-full flex flex-col">

      {/* Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0 sm:space-x-4">
        <div className="flex flex-col sm:flex-row sm:items-center space-y-4 sm:space-y-0 sm:space-x-4">
          {/* Source Filter */}
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

      {/* Alerts List and Detail View */}
      <div className="flex-grow flex flex-col overflow-hidden pb-2">
        {selectedAlert && (isNarrowViewport || isFullWidth) ? (
          <div className="flex-grow overflow-hidden">
            {renderSelectedAlert({
              alerts,
              selectedAlert,
              isFullWidth,
              isNarrowViewport,
              setSelectedAlert,
              setIsFullWidth,
              getBadgeVariant,
              getSeverityColor
            })}
          </div>
        ) : (
          <div className={`flex ${isNarrowViewport ? 'flex-col' : 'space-x-6'} h-full`}>
            <div className={`${isFullWidth ? 'hidden' : 'flex-1'} @container overflow-auto`}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[30%]">Source</TableHead>
                    <TableHead className="w-[40%] @[630px]:table-cell hidden">Alert</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell hidden">Severity</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell text-right hidden">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAlerts.map((alert) => (
                    <TableRow key={alert.id} onClick={() => handleAlertClick(alert.id)} className="cursor-pointer transition-colors duration-200 hover:bg-muted">
                      <TableCell className="font-medium pr-4">
                        <div>
                          {/* Narrow variant - visible below 630px */}
                          <div className="block @[630px]:hidden">
                            <div className="flex justify-between items-start mb-2">
                              <div className="font-semibold">{alert.source}</div>
                              <Badge 
                                className={`w-24 justify-center ${getBadgeVariant(alert.status)}`}
                              >
                                {alert.status}
                              </Badge>
                            </div>
                            <div className="text-sm text-muted-foreground mb-2">
                              {formatTimeAgo(alert.date, true)}
                            </div>
                            <div className="flex justify-between items-end">
                              <div className="text-sm text-muted-foreground">
                                <span className={`inline-block w-3 h-3 rounded-full ${getSeverityColor(alert.severity)}`}></span> {alert.severity}
                              </div>
                            </div>
                          </div>
                          {/* Wide variant - visible at 630px and above */}
                          <div className="hidden @[630px]:block">
                            {alert.source}
                            <div className="text-sm text-muted-foreground">
                              {formatTimeAgo(alert.date)}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell">{alert.message}</TableCell>
                      <TableCell className="hidden @[630px]:table-cell">
                        <div className="flex items-center gap-2">
                          <div className={`w-3 h-3 rounded-full ${getSeverityColor(alert.severity)}`}></div>
                          {alert.severity}
                        </div>
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-right">
                        <Badge 
                          className={`w-24 justify-center ${getBadgeVariant(alert.status)}`}
                        >
                          {alert.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {selectedAlert && !isNarrowViewport && !isFullWidth && (
              <div className="flex-1 overflow-hidden">
                {renderSelectedAlert({
                  alerts,
                  selectedAlert,
                  isFullWidth,
                  isNarrowViewport,
                  setSelectedAlert,
                  setIsFullWidth,
                  getBadgeVariant,
                  getSeverityColor
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function renderSelectedAlert({
  alerts,
  selectedAlert,
  isFullWidth,
  isNarrowViewport,
  setSelectedAlert,
  setIsFullWidth,
  getBadgeVariant,
  getSeverityColor
}: {
  alerts: { id: number; message: string; source: string; date: string; status: string; severity: string }[]; // Explicit type annotation
  selectedAlert: number | null;
  isFullWidth: boolean;
  isNarrowViewport: boolean;
  setSelectedAlert: (id: number | null) => void;
  setIsFullWidth: (isFullWidth: boolean) => void;
  getBadgeVariant: (status: string) => string;
  getSeverityColor: (severity: string) => string;
}) {
  const selectedAlertData = alerts.find(alert => alert.id === selectedAlert);

  if (!selectedAlertData) return null;

  return (
    <Card className="rounded-none sm:rounded-lg h-full flex flex-col bg-card-light border-none">
      <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between py-4 px-4 sm:px-6 space-y-0">
        <div>
          <h3 className="text-xl font-semibold">{selectedAlertData.message}</h3>
          <p className="text-sm text-muted-foreground">
            {selectedAlertData.source} • {formatTimeAgo(selectedAlertData.date)}
          </p>
        </div>
        <div className="flex ml-2">
          {!isNarrowViewport && (
            <Button variant="outline" size="icon" onClick={() => setIsFullWidth(!isFullWidth)}>
              {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
            </Button>
          )}
          <Button variant="outline" size="icon" onClick={() => {
            setSelectedAlert(null)
            setIsFullWidth(false)
          }} className="ml-2">
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
                  <div className={`w-3 h-3 rounded-full ${getSeverityColor(selectedAlertData.severity)}`} />
                  {selectedAlertData.severity}
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium">Status</p>
                <Badge 
                  className={`${getBadgeVariant(selectedAlertData.status)} w-24 justify-center`}
                >
                  {selectedAlertData.status}
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
                This alert was triggered based on the system's monitoring tools detecting a potential issue that requires attention or investigation.
                Please review the details and take appropriate action as needed.
              </p>
            </div>
            <div>
              <h4 className="text-md font-semibold">Actions Taken</h4>
              <hr className="my-2 border-t border-gray-200" />
              {/* Add actions content here if needed */}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

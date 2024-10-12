"use client"

import { useState, useMemo, useEffect } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X } from "lucide-react"
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

const items = [
  { id: 30, scorecard: "CS3 Services v2", score: 80, date: relativeDate(0, 0, 5), status: "new", results: 0, inferences: 0, cost: "$0.000" },
  { id: 29, scorecard: "CS3 Audigy", score: 89, date: relativeDate(0, 0, 15), status: "new", results: 0, inferences: 0, cost: "$0.000" },
  { id: 28, scorecard: "AW IB Sales", score: 96, date: relativeDate(0, 0, 30), status: "new", results: 0, inferences: 0, cost: "$0.000" },
  { id: 27, scorecard: "CS3 Nexstar v1", score: 88, date: relativeDate(0, 1, 0), status: "scoring...", results: 2, inferences: 4, cost: "$0.005" },
  { id: 26, scorecard: "SelectQuote Term Life v1", score: 83, date: relativeDate(0, 1, 30), status: "scoring...", results: 6, inferences: 24, cost: "$0.031" },
  { id: 25, scorecard: "AW IB Sales", score: 94, date: relativeDate(0, 2, 0), status: "scored", results: 19, inferences: 152, cost: "$0.199" },
  { id: 24, scorecard: "CS3 Audigy", score: 86, date: relativeDate(0, 3, 0), status: "scored", results: 17, inferences: 68, cost: "$0.089" },
  { id: 23, scorecard: "CS3 Services v2", score: 79, date: relativeDate(0, 4, 0), status: "scored", results: 16, inferences: 32, cost: "$0.042" },
  { id: 22, scorecard: "CS3 Nexstar v1", score: 91, date: relativeDate(0, 5, 0), status: "scored", results: 17, inferences: 68, cost: "$0.089" },
  { id: 21, scorecard: "SelectQuote Term Life v1", score: 89, date: relativeDate(0, 6, 0), status: "scored", results: 13, inferences: 52, cost: "$0.068" },
  { id: 20, scorecard: "CS3 Services v2", score: 82, date: relativeDate(1, 0, 0), status: "scored", results: 15, inferences: 30, cost: "$0.039" },
  { id: 19, scorecard: "AW IB Sales", score: 93, date: relativeDate(1, 2, 0), status: "scored", results: 18, inferences: 144, cost: "$0.188" },
  { id: 18, scorecard: "CS3 Audigy", score: 87, date: relativeDate(1, 4, 0), status: "scored", results: 16, inferences: 64, cost: "$0.084" },
  { id: 17, scorecard: "SelectQuote Term Life v1", score: 85, date: relativeDate(1, 6, 0), status: "scored", results: 14, inferences: 56, cost: "$0.073" },
  { id: 16, scorecard: "CS3 Nexstar v1", score: 90, date: relativeDate(1, 8, 0), status: "scored", results: 18, inferences: 72, cost: "$0.094" },
  { id: 15, scorecard: "CS3 Services v2", score: 81, date: relativeDate(1, 10, 0), status: "scored", results: 17, inferences: 34, cost: "$0.044" },
  { id: 14, scorecard: "AW IB Sales", score: 95, date: relativeDate(1, 12, 0), status: "scored", results: 20, inferences: 160, cost: "$0.209" },
  { id: 13, scorecard: "CS3 Audigy", score: 88, date: relativeDate(1, 14, 0), status: "scored", results: 18, inferences: 72, cost: "$0.094" },
  { id: 12, scorecard: "SelectQuote Term Life v1", score: 84, date: relativeDate(1, 16, 0), status: "scored", results: 15, inferences: 60, cost: "$0.078" },
  { id: 11, scorecard: "CS3 Nexstar v1", score: 92, date: relativeDate(1, 18, 0), status: "scored", results: 19, inferences: 76, cost: "$0.099" },
  { id: 10, scorecard: "CS3 Services v2", score: 83, date: relativeDate(1, 20, 0), status: "scored", results: 18, inferences: 36, cost: "$0.047" },
  { id: 9, scorecard: "AW IB Sales", score: 97, date: relativeDate(1, 22, 0), status: "scored", results: 21, inferences: 168, cost: "$0.219" },
  { id: 8, scorecard: "CS3 Audigy", score: 89, date: relativeDate(2, 0, 0), status: "scored", results: 19, inferences: 76, cost: "$0.099" },
  { id: 7, scorecard: "SelectQuote Term Life v1", score: 86, date: relativeDate(2, 2, 0), status: "scored", results: 16, inferences: 64, cost: "$0.084" },
  { id: 6, scorecard: "CS3 Nexstar v1", score: 93, date: relativeDate(2, 4, 0), status: "scored", results: 20, inferences: 80, cost: "$0.104" },
  { id: 5, scorecard: "CS3 Services v2", score: 84, date: relativeDate(2, 6, 0), status: "scored", results: 19, inferences: 38, cost: "$0.050" },
  { id: 4, scorecard: "AW IB Sales", score: 98, date: relativeDate(2, 8, 0), status: "scored", results: 22, inferences: 176, cost: "$0.230" },
  { id: 3, scorecard: "CS3 Audigy", score: 90, date: relativeDate(2, 10, 0), status: "scored", results: 20, inferences: 80, cost: "$0.104" },
  { id: 2, scorecard: "SelectQuote Term Life v1", score: 87, date: relativeDate(2, 12, 0), status: "scored", results: 17, inferences: 68, cost: "$0.089" },
  { id: 1, scorecard: "CS3 Nexstar v1", score: 94, date: relativeDate(2, 14, 0), status: "scored", results: 21, inferences: 84, cost: "$0.110" },
];

// Sort items by date, newest first
items.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

// Sample metadata and data for all items
const sampleMetadata = [
  { key: "Duration", value: "1022" },
  { key: "Dual Channel", value: "true" },
  { key: "Agent Name", value: "Johnny Appleseed" },
  { key: "Customer ID", value: "CUS-12345" },
  { key: "Call Type", value: "Inbound" },
  { key: "Department", value: "Customer Service" },
  { key: "Language", value: "English" },
  { key: "Recording ID", value: "REC-67890" },
];

const sampleTranscript = [
  { speaker: "Agent", text: "Thank you for calling our customer service. My name is Johnny. How may I assist you today?" },
  { speaker: "Caller", text: "Hi Johnny, I'm calling about an issue with my recent order. It hasn't arrived yet and it's been over a week." },
  { speaker: "Agent", text: "I apologize for the inconvenience. I'd be happy to look into that for you. May I have your order number, please?" },
  { speaker: "Caller", text: "Sure, it's ORDER123456." },
  { speaker: "Agent", text: "Thank you. I'm checking our system now. It looks like there was a slight delay in processing your order due to an inventory issue. However, I can see that it has now been shipped and is on its way to you." },
  { speaker: "Caller", text: "Oh, I see. When can I expect to receive it?" },
  { speaker: "Agent", text: "Based on the shipping information, you should receive your order within the next 2-3 business days. I apologize again for the delay. Is there anything else I can help you with today?" },
  { speaker: "Caller", text: "No, that's all. Thank you for the information." },
  { speaker: "Agent", text: "You're welcome. I appreciate your patience and understanding. If you have any further questions or concerns, please don't hesitate to call us back. Have a great day!" },
  { speaker: "Caller", text: "You too, goodbye." },
  { speaker: "Agent", text: "Goodbye and thank you for choosing our service." },
  { speaker: "Agent", text: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat." },
  { speaker: "Caller", text: "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum." },
  { speaker: "Agent", text: "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo." },
  { speaker: "Caller", text: "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt." },
  { speaker: "Agent", text: "Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam aliquam quaerat voluptatem." },
  { speaker: "Caller", text: "Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur?" },
  { speaker: "Agent", text: "Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur?" },
  { speaker: "Caller", text: "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident." },
  { speaker: "Agent", text: "Similique sunt in culpa qui officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio." },
  { speaker: "Caller", text: "Nam libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit quo minus id quod maxime placeat facere possimus, omnis voluptas assumenda est, omnis dolor repellendus." },
  { speaker: "Agent", text: "Temporibus autem quibusdam et aut officiis debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non recusandae. Itaque earum rerum hic tenetur a sapiente delectus." },
  { speaker: "Caller", text: "Ut aut reiciendis voluptatibus maiores alias consequatur aut perferendis doloribus asperiores repellat." },
];

export default function ItemsDashboard() {
  const [selectedItem, setSelectedItem] = useState<number | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)

  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }

    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)

    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  const filteredItems = useMemo(() => {
    return items.filter(item => 
      !selectedScorecard || item.scorecard === selectedScorecard
    )
  }, [selectedScorecard])

  const getRelativeTime = (dateString: string) => {
    const date = parseISO(dateString)
    return formatDistanceToNow(date, { addSuffix: true })
  }

  const handleItemClick = (itemId: number) => {
    setSelectedItem(itemId)
    if (isNarrowViewport) {
      setIsFullWidth(true)
    }
  }

  const getBadgeVariant = (status: string) => {
    switch (status) {
      case 'new':
        return 'default';
      case 'scoring...':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Items</h1>
        <p className="text-muted-foreground">
          Recent content items and their scoring status and results.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0 sm:space-x-4">
        <div className="flex flex-col sm:flex-row sm:items-center space-y-4 sm:space-y-0 sm:space-x-4">
          <Select onValueChange={(value) => setSelectedScorecard(value === "all" ? null : value)}>
            <SelectTrigger className="w-full sm:w-[280px] border border-secondary">
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
        </div>
      </div>

      <div className={`flex ${isNarrowViewport || isFullWidth ? 'flex-col' : 'space-x-6'}`}>
        <div className={`${isFullWidth && selectedItem ? 'hidden' : 'flex-1'}`}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]">Item</TableHead>
                <TableHead className="w-[15%] hidden sm:table-cell">Inferences</TableHead>
                <TableHead className="w-[15%] hidden sm:table-cell">Results</TableHead>
                <TableHead className="w-[15%] hidden sm:table-cell">Cost</TableHead>
                <TableHead className="w-[15%] hidden sm:table-cell">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredItems.map((item) => (
                <TableRow key={item.id} onClick={() => handleItemClick(item.id)} className="cursor-pointer">
                  <TableCell className="font-medium sm:pr-4">
                    <div className="sm:hidden">
                      <div className="flex justify-between items-start mb-2">
                        <div className="font-semibold">{item.scorecard}</div>
                        <Badge 
                          variant={getBadgeVariant(item.status)}
                          className="w-24 justify-center"
                        >
                          {item.status}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted-foreground mb-2">{getRelativeTime(item.date)}</div>
                      <div className="flex justify-between items-end">
                        <div className="text-sm text-muted-foreground">
                          {item.inferences} inferences<br />
                          {item.results} results
                        </div>
                        <div className="font-semibold">{item.cost}</div>
                      </div>
                    </div>
                    <div className="hidden sm:block">
                      {item.scorecard}
                      <div className="text-sm text-muted-foreground">{getRelativeTime(item.date)}</div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">{item.inferences}</TableCell>
                  <TableCell className="hidden sm:table-cell">{item.results}</TableCell>
                  <TableCell className="hidden sm:table-cell">{item.cost}</TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <Badge 
                      variant={getBadgeVariant(item.status)}
                      className="w-24 justify-center"
                    >
                      {item.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {selectedItem && (
          <div className={`${isFullWidth ? 'w-full' : 'flex-1'} ${isNarrowViewport || isFullWidth ? 'mx-0' : ''}`}>
            <Card className={`rounded-none sm:rounded-lg flex flex-col h-full max-h-[calc(100vh-8rem)]`}>
              <CardHeader className="flex flex-row items-center justify-between py-4 px-4 sm:px-6">
                <div className="space-y-1">
                  <h3 className="text-2xl font-semibold">{items.find(item => item.id === selectedItem)?.scorecard}</h3>
                  <p className="text-sm text-muted-foreground">
                    {getRelativeTime(items.find(item => item.id === selectedItem)?.date || '')}
                  </p>
                </div>
                <div className="flex space-x-2">
                  {!isNarrowViewport && (
                    <Button variant="outline" size="icon" onClick={() => setIsFullWidth(!isFullWidth)}>
                      {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                    </Button>
                  )}
                  <Button variant="outline" size="icon" onClick={() => {
                    setSelectedItem(null)
                    setIsFullWidth(false)
                  }}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex-grow overflow-auto px-4 sm:px-6">
                {selectedItem && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm font-medium">Inferences</p>
                        <p>{items.find(item => item.id === selectedItem)?.inferences}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">Status</p>
                        <Badge 
                          variant={items.find(item => item.id === selectedItem)?.status === 'new' ? 'default' : items.find(item => item.id === selectedItem)?.status === 'scoring...' ? 'secondary' : 'outline'}
                        >
                          {items.find(item => item.id === selectedItem)?.status}
                        </Badge>
                      </div>
                      <div>
                        <p className="text-sm font-medium">Results</p>
                        <p>{items.find(item => item.id === selectedItem)?.results}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium">Cost</p>
                        <p>{items.find(item => item.id === selectedItem)?.cost}</p>
                      </div>
                    </div>
                    <div>
                      <h4 className="text-md font-semibold">Metadata</h4>
                      <hr className="my-1 border-t border-gray-200" />
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
                      <h4 className="text-md font-semibold">Data</h4>
                      <hr className="my-1 border-t border-gray-200" />
                      <div className="space-y-2">
                        {sampleTranscript.map((line, index) => (
                          <p key={index} className="text-sm">
                            <span className="font-semibold">{line.speaker}: </span>
                            {line.text}
                          </p>
                        ))}
                      </div>
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
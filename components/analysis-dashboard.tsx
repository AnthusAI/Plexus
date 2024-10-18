"use client"
import React from "react"
import { useState, useMemo, useEffect, useRef, useCallback } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown } from "lucide-react"
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
import { TimeRangeSelector, TimeRangeOption } from "@/components/time-range-selector"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import ReactMarkdown from 'react-markdown'
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import Link from 'next/link'
import { FilterControl, FilterConfig } from "@/components/filter-control"
import { Progress } from "@/components/ui/progress"
import { MoveUpRight } from "lucide-react"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { ResponsiveContainer, PieChart, Pie } from "recharts"

const chartConfig = {
  positive: { label: "Positive", color: "var(--true)" },
  negative: { label: "Negative", color: "var(--false)" },
}

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
  { id: 30, scorecard: "CS3 Services v2", score: 80, date: relativeDate(0, 0, 5), status: "new", results: 0, inferences: 0, cost: "$0.000", progress: 66, type: "Prompt Optimization" },
  { id: 29, scorecard: "CS3 Audigy", score: 89, date: relativeDate(0, 0, 15), status: "new", results: 0, inferences: 0, cost: "$0.000", progress: 50, type: "Error Analysis" },
  { id: 28, scorecard: "AW IB Sales", score: 96, date: relativeDate(0, 0, 30), status: "new", results: 0, inferences: 0, cost: "$0.000", progress: 80, type: "Prompt Optimization" },
  { id: 27, scorecard: "CS3 Nexstar v1", score: 88, date: relativeDate(0, 1, 0), status: "error", results: 2, inferences: 4, cost: "$0.005", progress: 100, type: "IAA Analysis" },
  { id: 26, scorecard: "SelectQuote Term Life v1", score: 83, date: relativeDate(0, 1, 30), status: "scoring...", results: 6, inferences: 24, cost: "$0.031", progress: 100, type: "Hyperparameter Optimization" },
  { id: 25, scorecard: "AW IB Sales", score: 94, date: relativeDate(0, 2, 0), status: "scored", results: 19, inferences: 152, cost: "$0.199", progress: 100, type: "Error Analysis" },
  { id: 24, scorecard: "CS3 Audigy", score: 86, date: relativeDate(0, 3, 0), status: "scored", results: 17, inferences: 68, cost: "$0.089", progress: 100, type: "Prompt Optimization" },
  { id: 23, scorecard: "CS3 Services v2", score: 79, date: relativeDate(0, 4, 0), status: "scored", results: 16, inferences: 32, cost: "$0.042", progress: 100, type: "Hyperparameter Optimization" },
  { id: 22, scorecard: "CS3 Nexstar v1", score: 91, date: relativeDate(0, 5, 0), status: "scored", results: 17, inferences: 68, cost: "$0.089", progress: 100, type: "IAA Analysis" },
  { id: 21, scorecard: "SelectQuote Term Life v1", score: 89, date: relativeDate(0, 6, 0), status: "scored", results: 13, inferences: 52, cost: "$0.068", progress: 100, type: "Error Analysis" },
  { id: 20, scorecard: "CS3 Services v2", score: 82, date: relativeDate(1, 0, 0), status: "scored", results: 15, inferences: 30, cost: "$0.039", progress: 100, type: "Prompt Optimization" },
  { id: 19, scorecard: "AW IB Sales", score: 93, date: relativeDate(1, 2, 0), status: "scored", results: 18, inferences: 144, cost: "$0.188", progress: 100, type: "Error Analysis" },
  { id: 18, scorecard: "CS3 Audigy", score: 87, date: relativeDate(1, 4, 0), status: "scored", results: 16, inferences: 64, cost: "$0.084", progress: 100, type: "Prompt Optimization" },
  { id: 17, scorecard: "SelectQuote Term Life v1", score: 85, date: relativeDate(1, 6, 0), status: "scored", results: 14, inferences: 56, cost: "$0.073", progress: 100, type: "Hyperparameter Optimization" },
  { id: 16, scorecard: "CS3 Nexstar v1", score: 90, date: relativeDate(1, 8, 0), status: "scored", results: 18, inferences: 72, cost: "$0.094", progress: 100, type: "IAA Analysis" },
  { id: 15, scorecard: "CS3 Services v2", score: 81, date: relativeDate(1, 10, 0), status: "scored", results: 17, inferences: 34, cost: "$0.044", progress: 100, type: "Prompt Optimization" },
  { id: 14, scorecard: "AW IB Sales", score: 95, date: relativeDate(1, 12, 0), status: "scored", results: 20, inferences: 160, cost: "$0.209", progress: 100, type: "Error Analysis" },
  { id: 13, scorecard: "CS3 Audigy", score: 88, date: relativeDate(1, 14, 0), status: "scored", results: 18, inferences: 72, cost: "$0.094", progress: 100, type: "Prompt Optimization" },
  { id: 12, scorecard: "SelectQuote Term Life v1", score: 84, date: relativeDate(1, 16, 0), status: "scored", results: 15, inferences: 60, cost: "$0.078", progress: 100, type: "Hyperparameter Optimization" },
  { id: 11, scorecard: "CS3 Nexstar v1", score: 92, date: relativeDate(1, 18, 0), status: "scored", results: 19, inferences: 76, cost: "$0.099", progress: 100, type: "IAA Analysis" },
  { id: 10, scorecard: "CS3 Services v2", score: 83, date: relativeDate(1, 20, 0), status: "scored", results: 18, inferences: 36, cost: "$0.047", progress: 100, type: "Prompt Optimization" },
  { id: 9, scorecard: "AW IB Sales", score: 97, date: relativeDate(1, 22, 0), status: "scored", results: 21, inferences: 168, cost: "$0.219", progress: 100, type: "Error Analysis" },
  { id: 8, scorecard: "CS3 Audigy", score: 89, date: relativeDate(2, 0, 0), status: "scored", results: 19, inferences: 76, cost: "$0.099", progress: 100, type: "Prompt Optimization" },
  { id: 7, scorecard: "SelectQuote Term Life v1", score: 86, date: relativeDate(2, 2, 0), status: "scored", results: 16, inferences: 64, cost: "$0.084", progress: 100, type: "Hyperparameter Optimization" },
  { id: 6, scorecard: "CS3 Nexstar v1", score: 93, date: relativeDate(2, 4, 0), status: "scored", results: 20, inferences: 80, cost: "$0.104", progress: 100, type: "IAA Analysis" },
  { id: 5, scorecard: "CS3 Services v2", score: 84, date: relativeDate(2, 6, 0), status: "scored", results: 19, inferences: 38, cost: "$0.050", progress: 100, type: "Prompt Optimization" },
  { id: 4, scorecard: "AW IB Sales", score: 98, date: relativeDate(2, 8, 0), status: "scored", results: 22, inferences: 176, cost: "$0.230", progress: 100, type: "Error Analysis" },
  { id: 3, scorecard: "CS3 Audigy", score: 90, date: relativeDate(2, 10, 0), status: "scored", results: 20, inferences: 80, cost: "$0.104", progress: 100, type: "Prompt Optimization" },
  { id: 2, scorecard: "SelectQuote Term Life v1", score: 87, date: relativeDate(2, 12, 0), status: "scored", results: 17, inferences: 68, cost: "$0.089", progress: 100, type: "Hyperparameter Optimization" },
  { id: 1, scorecard: "CS3 Nexstar v1", score: 94, date: relativeDate(2, 14, 0), status: "scored", results: 21, inferences: 84, cost: "$0.110", progress: 100, type: "IAA Analysis" },
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
  { speaker: "Agent", text: "Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur?" },
  { speaker: "Caller", text: "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque corrupti quos dolores et quas molestias excepturi sint occaecati cupiditate non provident." },
  { speaker: "Agent", text: "Similique sunt in culpa qui officia deserunt mollitia animi, id est laborum et dolorum fuga. Et harum quidem rerum facilis est et expedita distinctio." },
  { speaker: "Caller", text: "Nam libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit quo minus id quod maxime placeat facere possimus, omnis voluptas assumenda est, omnis dolor repellendus." },
  { speaker: "Agent", text: "Temporibus autem quibusdam et aut officiis debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non recusandae. Itaque earum rerum hic tenetur a sapiente delectus." },
  { speaker: "Caller", text: "Ut aut reiciendis voluptatibus maiores alias consequatur aut perferendis doloribus asperiores repellat." },
];

const ITEMS_TIME_RANGE_OPTIONS: TimeRangeOption[] = [
  { value: "recent", label: "Recent" },
  { value: "review", label: "With Feedback" },
  { value: "custom", label: "Custom" },
]

// Add this to the existing items array or create a new constant
const sampleScoreResults = [
  {
    section: "Technical",
    scores: [
      { name: "Scoreable Call", value: "Yes", explanation: "The call meets all criteria to be scored. This includes having clear audio, being of sufficient length, and containing relevant content for evaluation." },
      { name: "Call Efficiency", value: "Yes", explanation: `The agent managed the call time effectively while still addressing the customer's needs:

**Proper Call Control:** The agent skillfully guided the conversation, keeping it on track without being abrupt or dismissive.

**Efficient Information Gathering:** The agent asked concise, relevant questions to quickly understand the customer's situation without unnecessary repetition.

**Timely Resolution:** The agent resolved the main issue within an appropriate timeframe, balancing thoroughness with efficiency.

**Effective Use of Tools:** The agent demonstrated proficiency with their systems, quickly accessing and updating information without causing undue delays.

**Appropriate Small Talk:** The agent maintained a friendly demeanor while keeping small talk brief and relevant, striking a good balance between building rapport and maintaining efficiency.` },
    ]
  },
  {
    section: "Sales",
    scores: [
      { name: "Assumptive Close", value: "No", explanation: "The agent did not use an assumptive close technique. Instead, they used a more consultative approach, asking for the customer's decision rather than assuming it." },
      { name: "Problem Resolution", value: "Yes", explanation: `The agent effectively resolved the customer's issue:

**Issue Identification:** The agent quickly and accurately identified the core problem by asking probing questions and actively listening to the customer's responses.

**Knowledge Application:** The agent demonstrated a thorough understanding of the product/service and company policies, applying this knowledge to address the customer's specific situation.

**Step-by-Step Solution:** The agent provided a clear, logical sequence of steps to resolve the issue, ensuring the customer understood each part of the process.

**Confirmation:** The agent verified that the solution met the customer's needs by asking for confirmation and addressing any lingering concerns.

**Future Prevention:** The agent offered advice on how to prevent similar issues in the future, adding value beyond just solving the immediate problem.` },
    ]
  },
  {
    section: "Soft Skills",
    scores: [
      { name: "Rapport", value: "Yes", explanation: `The agent demonstrated excellent rapport-building skills throughout the call:

**Active Listening:** The agent consistently acknowledged the customer's statements and asked relevant follow-up questions, showing they were fully engaged in the conversation.

**Empathy:** The agent expressed understanding and validation of the customer's concerns, using phrases like "I understand how frustrating that must be" and "I can see why that would be important to you."

**Encouragement:** The agent provided positive reinforcement throughout the call, praising the customer's efforts and decisions with comments like "That's a great question" and "You're on the right track."

**Personalization:** The agent tailored their approach to the customer's specific situation, referencing previous interactions and using the customer's name naturally throughout the conversation.` },
      { name: "Friendly Greeting", value: "Yes", explanation: "The agent provided a warm and professional greeting. They used a pleasant tone of voice, introduced themselves clearly, and made the customer feel welcome." },
      { name: "Agent Offered Name", value: "Yes", explanation: "The agent clearly stated their name at the beginning of the call. This was done in a natural and friendly manner, helping to establish a personal connection with the customer." },
      { name: "Temperature Check", value: "Yes", explanation: "The agent asked about the customer's satisfaction during the call. This was done at an appropriate time and in a way that invited honest feedback from the customer." },
    ]
  },
  {
    section: "Compliance",
    scores: [
      { name: "DNC Requested", value: "No", explanation: "The customer did not request to be added to the Do Not Call list. The agent properly handled any questions about contact preferences without any DNC requests being made." },
      { 
        name: "Profanity", 
        value: "No", 
        explanation: "No profanity was detected during the call. Both the agent and the customer maintained professional and respectful language throughout the entire conversation.",
        isAnnotated: true,
        annotations: [
          {
            value: "No",
            explanation: "No profanity was detected during the call. Both the agent and the customer maintained professional and respectful language throughout the entire conversation.",
            annotation: "The word 'dangit' is not profanity by our standards.",
            timestamp: relativeDate(0, 0, 5),
            user: {
              name: "Ryan Porter",
              initials: "RP"
            }
          },
          {
            value: "Yes",
            explanation: "Profanity was detected during the call. The agent used the word 'dangit!' which was flagged as potentially inappropriate language.",
            timestamp: relativeDate(0, 0, 10),
            isSystem: true
          }
        ]
      },
      { name: "Agent Offered Legal Advice", value: "No", explanation: "The agent did not offer any legal advice during the call, which is outside their scope of expertise and could potentially lead to compliance issues." },
      { name: "Agent Offered Guarantees", value: "No", explanation: "The agent did not make any unauthorized guarantees or promises that could be construed as binding commitments by the company." },
    ]
  }
];

const renderRichText = (text: string) => {
  return (
    <ReactMarkdown
      components={{
        p: ({node, ...props}) => <p className="mb-2" {...props} />,
        strong: ({node, ...props}) => <strong className="font-semibold" {...props} />,
        ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-2" {...props} />,
        li: ({node, ...props}) => <li className="mb-1" {...props} />,
      }}
    >
      {text}
    </ReactMarkdown>
  )
}

const renderProgressBar = (progress: number, truePart: number, falsePart: number, isAccuracy: boolean) => {
  const accuracy = Math.round((truePart / (truePart + falsePart)) * 100);
  const trueWidth = (accuracy / 100) * progress;
  const falseWidth = progress - trueWidth;

  return (
    <div className="relative w-full h-6 bg-neutral rounded-full">
      {isAccuracy ? (
        <>
          <div
            className="absolute top-0 left-0 h-full bg-true flex items-center pl-2 text-xs text-primary-foreground font-medium"
            style={{ width: `${trueWidth}%`, borderTopLeftRadius: 'inherit', borderBottomLeftRadius: 'inherit' }}
          >
            {accuracy}%
          </div>
          <div
            className="absolute top-0 h-full bg-false"
            style={{ 
              left: `${trueWidth}%`, 
              width: `${falseWidth}%`,
              borderTopRightRadius: 'inherit',
              borderBottomRightRadius: 'inherit'
            }}
          />
        </>
      ) : (
        <div
          className="absolute top-0 left-0 h-full bg-secondary flex items-center pl-2 text-xs text-primary-foreground font-medium"
          style={{ width: `${progress}%`, borderRadius: 'inherit' }}
        >
          {progress}%
        </div>
      )}
    </div>
  )
}

const getBadgeVariant = (status: string, progress: number) => {
  if (progress < 100) {
    return 'bg-secondary text-secondary-foreground h-6';
  } else {
    return 'bg-true text-primary-foreground h-6';
  }
};

const getStatusText = (status: string, progress: number) => {
  if (progress < 100) {
    return 'running...';
  } else {
    return 'completed';
  }
};

export default function AnalysisDashboard() {
  const [selectedItem, setSelectedItem] = useState<number | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)

  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }

    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)

    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  const handleItemClick = (itemId: number) => {
    setSelectedItem(itemId)
    if (isNarrowViewport) {
      setIsFullWidth(true)
    }
  }

  const getRelativeTime = (dateString: string) => {
    const date = parseISO(dateString)
    return formatDistanceToNow(date, { addSuffix: true })
  }

  const renderAnalysisItem = (item: any) => (
    <TableRow key={item.id} onClick={() => handleItemClick(item.id)} className="cursor-pointer transition-colors duration-200 hover:bg-muted">
      <TableCell className="font-medium sm:pr-4">
        <div className="sm:hidden">
          <div className="font-semibold">{item.scorecard}</div>
          <div className="text-sm text-muted-foreground">{getRelativeTime(item.date)}</div>
        </div>
        <div className="hidden sm:block">
          {item.scorecard}
          <div className="text-sm text-muted-foreground">{getRelativeTime(item.date)}</div>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant="secondary" className="bg-neutral text-primary-foreground">
          {item.type}
        </Badge>
      </TableCell>
      <TableCell className="text-right">{item.inferences}</TableCell>
      <TableCell className="text-right">{item.cost}</TableCell>
      <TableCell className="w-[15%]">
        <Badge className={getBadgeVariant(item.status, item.progress)}>
          {getStatusText(item.status, item.progress)}
        </Badge>
      </TableCell>
    </TableRow>
  )

  const renderSelectedItem = () => {
    const selectedItemData = items.find(item => item.id === selectedItem)
    if (!selectedItemData) return null

    return (
      <Card className="rounded-none sm:rounded-lg h-full flex flex-col bg-card-light border-none">
        <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between py-4 px-4 sm:px-6 space-y-0">
          <div>
            <h2 className="text-xl font-semibold">{selectedItemData.scorecard}</h2>
            <p className="text-sm text-muted-foreground">
              {formatDistanceToNow(parseISO(selectedItemData.date), { addSuffix: true })}
            </p>
          </div>
          <div className="flex ml-2">
            {!isNarrowViewport && (
              <Button variant="outline" size="icon" onClick={() => setIsFullWidth(!isFullWidth)}>
                {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
              </Button>
            )}
            <Button variant="outline" size="icon" onClick={() => {
              setSelectedItem(null)
              setIsFullWidth(false)
            }} className="ml-2">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex-grow overflow-auto px-4 sm:px-6 pb-4">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-medium">Type</p>
                <Badge variant="secondary" className="bg-neutral text-primary-foreground">
                  {selectedItemData.type}
                </Badge>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium">Status</p>
                <Badge className={getBadgeVariant(selectedItemData.status, selectedItemData.progress)}>
                  {getStatusText(selectedItemData.status, selectedItemData.progress)}
                </Badge>
              </div>
              <div>
                <p className="text-sm font-medium">Inferences</p>
                <p>{selectedItemData.inferences}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium">Cost</p>
                <p>{selectedItemData.cost}</p>
              </div>
            </div>
            
            {/* Progress indicator */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <div className="font-semibold">Progress: {selectedItemData.progress}%</div>
                {selectedItemData.status !== 'completed' && <div>Elapsed Time: 00:45:30</div>}
              </div>
              <Progress value={selectedItemData.progress} className="w-full h-6" />
              {selectedItemData.status !== 'completed' && (
                <div className="text-xs text-right">
                  Estimated Time Remaining: 00:05:00
                </div>
              )}
            </div>
            
            {renderAnalysisDetails(selectedItemData)}
          </div>
        </CardContent>
      </Card>
    )
  }

  const renderAnalysisDetails = (item: any) => {
    return (
      <div className="space-y-4">
        {/* Specific details for each type */}
        {(() => {
          switch (item.type) {
            case "Error Analysis":
              return (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Error Analysis</h3>
                  <div className="bg-muted p-4 rounded-md">
                    <p><strong>Total items investigated:</strong> 500</p>
                    <p><strong>Items with feedback:</strong> 327 (65.4%)</p>
                  </div>
                  <h4 className="text-md font-semibold mt-4">Key Insights:</h4>
                  <div className="space-y-4">
                    <div className="bg-muted p-4 rounded-md">
                      <p><strong>Contextual Misinterpretation:</strong> Our analysis reveals that the classifier often flags mild expletives (e.g., "darn", "heck") as profanity, while the client's standards consider these acceptable. This suggests that our prompt may be too strict and lacks nuance in understanding the severity of different terms within the client's cultural context.</p>
                    </div>
                    <div className="bg-muted p-4 rounded-md">
                      <p><strong>Idiomatic Expressions:</strong> We've identified a trend where certain idiomatic expressions (e.g., "what the hell", "damn right") are being classified as profanity, despite being considered mild and acceptable in the client's guidelines. This indicates that our prompt needs refinement to better understand and interpret common phrases that may contain traditionally profane words but are used in non-offensive contexts.</p>
                    </div>
                    <div className="bg-muted p-4 rounded-md">
                      <p><strong>False Negatives in Euphemisms:</strong> The analysis shows that our classifier is missing subtle euphemisms and replacements for profane words (e.g., "frick", "shoot") that the client considers unprofessional. This suggests that our prompt should be expanded to recognize a broader range of substitutions and near-profanities that may not be explicitly profane but still fall outside the client's acceptable language standards.</p>
                    </div>
                  </div>
                </div>
              )
            case "IAA Analysis":
              return (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Inter-Annotator Agreement</h3>
                  <div className="flex items-center justify-between">
                    <span>Krippendorff's Alpha:</span>
                    <span className="font-semibold">0.82</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Fleiss' Kappa:</span>
                    <span className="font-semibold">0.79</span>
                  </div>
                </div>
              )
            case "Prompt Optimization":
              return (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Prompt Performance</h3>
                  <div className="flex items-center justify-between">
                    <div className="font-semibold">Accuracy</div>
                    <div className="flex items-center">
                      <span>75%</span>
                      <MoveUpRight className="h-6 w-6 mx-1" />
                      <span>92%</span>
                    </div>
                  </div>
                  <div className="flex space-x-4 justify-center">
                    <div className="text-center">
                      <div className="text-sm font-medium mb-1">Before</div>
                      <ChartContainer config={chartConfig} className="h-[80px] w-[80px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Pie
                              data={[
                                { category: "Positive", value: 75, fill: "var(--true)" },
                                { category: "Negative", value: 25, fill: "var(--false)" },
                              ]}
                              dataKey="value"
                              nameKey="category"
                              outerRadius={30}
                              fill="var(--chart-1)"
                            />
                            <Pie
                              data={[
                                { category: "Positive", value: 50, fill: "var(--true)" },
                                { category: "Negative", value: 50, fill: "var(--false)" },
                              ]}
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
                              data={[
                                { category: "Positive", value: 92, fill: "var(--true)" },
                                { category: "Negative", value: 8, fill: "var(--false)" },
                              ]}
                              dataKey="value"
                              nameKey="category"
                              outerRadius={30}
                              fill="var(--chart-1)"
                            />
                            <Pie
                              data={[
                                { category: "Positive", value: 50, fill: "var(--true)" },
                                { category: "Negative", value: 50, fill: "var(--false)" },
                              ]}
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
                </div>
              )
            case "Hyperparameter Optimization":
              return (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Best Hyperparameters</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm font-medium">Learning Rate</p>
                      <p>0.001</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium">Batch Size</p>
                      <p>32</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium">Epochs</p>
                      <p>100</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium">Dropout</p>
                      <p>0.2</p>
                    </div>
                  </div>
                </div>
              )
            default:
              return null
          }
        })()}
      </div>
    )
  }

  const PieChartVisualization = ({ data }: { data: { name: string; value: number }[] }) => (
    <ChartContainer config={chartConfig} className="h-[200px] w-[200px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <ChartTooltip content={<ChartTooltipContent />} />
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            outerRadius={80}
            fill="var(--chart-1)"
            label
          />
        </PieChart>
      </ResponsiveContainer>
    </ChartContainer>
  )

  const BeforeAfterChart = ({ before, after }: { before: number; after: number }) => (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="font-semibold">Accuracy</div>
        <div className="flex items-center">
          <span>{before}%</span>
          <MoveUpRight className="h-6 w-6 mx-1" />
          <span>{after}%</span>
        </div>
      </div>
      <Progress value={after} className="w-full h-4" />
    </div>
  )

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex-grow flex flex-col overflow-hidden pb-2">
        {selectedItem && (isNarrowViewport || isFullWidth) ? (
          <div className="flex-grow overflow-hidden">
            {renderSelectedItem()}
          </div>
        ) : (
          <div className={`flex ${isNarrowViewport ? 'flex-col' : 'space-x-6'} h-full`}>
            <div className={`${isFullWidth ? 'hidden' : 'flex-1'} overflow-auto`}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[35%]">Analysis</TableHead>
                    <TableHead className="w-[15%]">Type</TableHead>
                    <TableHead className="w-[15%] text-right">Inferences</TableHead>
                    <TableHead className="w-[15%] text-right">Cost</TableHead>
                    <TableHead className="w-[20%] text-left">Progress</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map(renderAnalysisItem)}
                </TableBody>
              </Table>
            </div>

            {selectedItem && !isNarrowViewport && !isFullWidth && (
              <div className="flex-1 overflow-hidden">
                {renderSelectedItem()}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
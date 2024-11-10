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
import { TimeRangeSelector } from "@/components/time-range-selector"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import ReactMarkdown from 'react-markdown'
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import Link from 'next/link'
import { FilterControl, FilterConfig } from "@/components/filter-control"
import ScorecardContext from "@/components/ScorecardContext"
import ItemContext from "@/components/ItemContext"
import ItemDetail from './ItemDetail'
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

// First, let's define an interface for the item
interface Item {
  id: number;
  scorecard: string;
  score: number;
  date: string;
  status: string;
  results: number;
  inferences: number;
  cost: string;
  scoreResults?: typeof sampleScoreResults;  // Make this optional
}

// Rename this to initialItems
const initialItems: Item[] = [
  { id: 30, scorecard: "CS3 Services v2", score: 80, date: relativeDate(0, 0, 5), status: "New", results: 0, inferences: 0, cost: "$0.000" },
  { id: 29, scorecard: "CS3 Audigy", score: 89, date: relativeDate(0, 0, 15), status: "New", results: 0, inferences: 0, cost: "$0.000" },
  { id: 28, scorecard: "AW IB Sales", score: 96, date: relativeDate(0, 0, 30), status: "New", results: 0, inferences: 0, cost: "$0.000" },
  { id: 27, scorecard: "CS3 Nexstar v1", score: 88, date: relativeDate(0, 1, 0), status: "Error", results: 2, inferences: 4, cost: "$0.005" },
  { id: 26, scorecard: "SelectQuote Term Life v1", score: 83, date: relativeDate(0, 1, 30), status: "Scoring", results: 6, inferences: 24, cost: "$0.031" },
  { id: 25, scorecard: "AW IB Sales", score: 94, date: relativeDate(0, 2, 0), status: "Done", results: 19, inferences: 152, cost: "$0.199" },
  { id: 24, scorecard: "CS3 Audigy", score: 86, date: relativeDate(0, 3, 0), status: "Done", results: 17, inferences: 68, cost: "$0.089" },
  { id: 23, scorecard: "CS3 Services v2", score: 79, date: relativeDate(0, 4, 0), status: "Done", results: 16, inferences: 32, cost: "$0.042" },
  { id: 22, scorecard: "CS3 Nexstar v1", score: 91, date: relativeDate(0, 5, 0), status: "Done", results: 17, inferences: 68, cost: "$0.089" },
  { id: 21, scorecard: "SelectQuote Term Life v1", score: 89, date: relativeDate(0, 6, 0), status: "Done", results: 13, inferences: 52, cost: "$0.068" },
  { id: 20, scorecard: "CS3 Services v2", score: 82, date: relativeDate(1, 0, 0), status: "Done", results: 15, inferences: 30, cost: "$0.039" },
  { id: 19, scorecard: "AW IB Sales", score: 93, date: relativeDate(1, 2, 0), status: "Done", results: 18, inferences: 144, cost: "$0.188" },
  { id: 18, scorecard: "CS3 Audigy", score: 87, date: relativeDate(1, 4, 0), status: "Done", results: 16, inferences: 64, cost: "$0.084" },
  { id: 17, scorecard: "SelectQuote Term Life v1", score: 85, date: relativeDate(1, 6, 0), status: "Done", results: 14, inferences: 56, cost: "$0.073" },
  { id: 16, scorecard: "CS3 Nexstar v1", score: 90, date: relativeDate(1, 8, 0), status: "Done", results: 18, inferences: 72, cost: "$0.094" },
  { id: 15, scorecard: "CS3 Services v2", score: 81, date: relativeDate(1, 10, 0), status: "Done", results: 17, inferences: 34, cost: "$0.044" },
  { id: 14, scorecard: "AW IB Sales", score: 95, date: relativeDate(1, 12, 0), status: "Done", results: 20, inferences: 160, cost: "$0.209" },
  { id: 13, scorecard: "CS3 Audigy", score: 88, date: relativeDate(1, 14, 0), status: "Done", results: 18, inferences: 72, cost: "$0.094" },
  { id: 12, scorecard: "SelectQuote Term Life v1", score: 84, date: relativeDate(1, 16, 0), status: "Done", results: 15, inferences: 60, cost: "$0.078" },
  { id: 11, scorecard: "CS3 Nexstar v1", score: 92, date: relativeDate(1, 18, 0), status: "Done", results: 19, inferences: 76, cost: "$0.099" },
  { id: 10, scorecard: "CS3 Services v2", score: 83, date: relativeDate(1, 20, 0), status: "Done", results: 18, inferences: 36, cost: "$0.047" },
  { id: 9, scorecard: "AW IB Sales", score: 97, date: relativeDate(1, 22, 0), status: "Done", results: 21, inferences: 168, cost: "$0.219" },
  { id: 8, scorecard: "CS3 Audigy", score: 89, date: relativeDate(2, 0, 0), status: "Done", results: 19, inferences: 76, cost: "$0.099" },
  { id: 7, scorecard: "SelectQuote Term Life v1", score: 86, date: relativeDate(2, 2, 0), status: "Done", results: 16, inferences: 64, cost: "$0.084" },
  { id: 6, scorecard: "CS3 Nexstar v1", score: 93, date: relativeDate(2, 4, 0), status: "Done", results: 20, inferences: 80, cost: "$0.104" },
  { id: 5, scorecard: "CS3 Services v2", score: 84, date: relativeDate(2, 6, 0), status: "Done", results: 19, inferences: 38, cost: "$0.050" },
  { id: 4, scorecard: "AW IB Sales", score: 98, date: relativeDate(2, 8, 0), status: "Done", results: 22, inferences: 176, cost: "$0.230" },
  { id: 3, scorecard: "CS3 Audigy", score: 90, date: relativeDate(2, 10, 0), status: "Done", results: 20, inferences: 80, cost: "$0.104" },
  { id: 2, scorecard: "SelectQuote Term Life v1", score: 87, date: relativeDate(2, 12, 0), status: "Done", results: 17, inferences: 68, cost: "$0.089" },
  { id: 1, scorecard: "CS3 Nexstar v1", score: 94, date: relativeDate(2, 14, 0), status: "Done", results: 21, inferences: 84, cost: "$0.110" },
];

// Sort items by date, newest first
initialItems.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

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

const ITEMS_TIME_RANGE_OPTIONS = [
  { value: "recent", label: "Recent" },
  { value: "review", label: "With Feedback" },
  { value: "custom", label: "Custom" },
]

// Add this to the existing items array or create a new constant
const sampleScoreResults = [
  {
    section: "Technical",
    scores: [
      { 
        name: "Scoreable Call", 
        value: "Yes", 
        explanation: "The call meets all criteria to be scored...", 
        allowFeedback: true
      },
      { 
        name: "Call Efficiency", 
        value: "Yes", 
        explanation: `The agent managed the call time effectively...`, 
        allowFeedback: true
      },
    ]
  },
  {
    section: "Sales",
    scores: [
      { 
        name: "Assumptive Close", 
        value: "No", 
        explanation: "The agent did not use an assumptive close technique...", 
        allowFeedback: true
      },
      { 
        name: "Problem Resolution", 
        value: "Yes", 
        explanation: `The agent effectively resolved the customer's issue...`, 
        allowFeedback: true
      },
    ]
  },
  {
    section: "Soft Skills",
    scores: [
      { 
        name: "Rapport", 
        value: "Yes", 
        explanation: `The agent demonstrated excellent rapport-building skills...`, 
        allowFeedback: true
      },
      { 
        name: "Friendly Greeting", 
        value: "Yes", 
        explanation: "The agent provided a warm and professional greeting...", 
        allowFeedback: true
      },
      { 
        name: "Agent Offered Name", 
        value: "Yes", 
        explanation: "The agent clearly stated their name...", 
        allowFeedback: true
      },
      { 
        name: "Temperature Check", 
        value: "Yes", 
        explanation: "The agent asked about the customer's satisfaction...", 
        allowFeedback: true
      },
    ]
  },
  {
    section: "Compliance",
    scores: [
      { 
        name: "DNC Requested", 
        value: "No", 
        explanation: "The customer did not request to be added to the Do Not Call list...", 
        allowFeedback: true
      },
      { 
        name: "Profanity", 
        value: "No", 
        explanation: "No profanity was detected during the call...",
        isAnnotated: true,
        allowFeedback: true,
        annotations: [
          {
            value: "No",
            explanation: "No profanity was detected...",
            annotation: "The word 'dangit' is not profanity by our standards.",
            timestamp: relativeDate(0, 0, 5),
            user: {
              name: "Ryan Porter",
              initials: "RP"
            }
          },
          {
            value: "Yes",
            explanation: "Profanity was detected during the call...",
            timestamp: relativeDate(0, 0, 10),
            isSystem: true
          }
        ]
      },
      { 
        name: "Agent Offered Legal Advice", 
        value: "No", 
        explanation: "The agent did not offer any legal advice...", 
        allowFeedback: true
      },
      { 
        name: "Agent Offered Guarantees", 
        value: "No", 
        explanation: "The agent did not make any unauthorized guarantees...", 
        allowFeedback: true
      },
    ]
  },
  {
    section: "Computed Scores",
    scores: [
      { 
        name: "Compliance", 
        value: "94%", 
        explanation: "This score represents the overall compliance level...",
        allowFeedback: false
      },
      { 
        name: "Soft Skills", 
        value: "87%", 
        explanation: "This score evaluates the agent's interpersonal abilities...",
        allowFeedback: false
      },
    ]
  },
];

// Define the User interface
interface User {
  name: string;
  initials: string;
}

// Define the Score type
interface Score {
  name: string;
  value: string;
  explanation: string;
  isAnnotated?: boolean;
  annotations?: any[]; // Keep this if you want to store multiple annotations
  annotation?: string; // Add this line if you want to keep a single annotation
  allowFeedback?: boolean;
  isSystem?: boolean;
  timestamp?: string;
  user?: User;
}

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

// Add these interfaces near the top with other interfaces
interface Annotation {
  value: string;
  explanation: string;
  annotation?: string;
  timestamp: string;
  user?: {
    name: string;
    initials: string;
  };
  isSystem?: boolean;
  isThumbsUp: boolean;
}

// Add this function before the ItemsDashboard component
const getRelativeTime = (dateString: string | undefined): string => {
  if (!dateString) return 'Unknown date';
  return formatTimeAgo(dateString);
};

export default function ItemsDashboard() {
  const [selectedItem, setSelectedItem] = useState<number | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [isMetadataExpanded, setIsMetadataExpanded] = useState(false)
  const [isDataExpanded, setIsDataExpanded] = useState(false)
  const [selectedScore, setSelectedScore] = useState<string | null>(null);
  const [expandedExplanations, setExpandedExplanations] = useState<string[]>([]);
  const [truncatedExplanations, setTruncatedExplanations] = useState<{[key: string]: string}>({});
  const explanationRefs = useRef<{[key: string]: HTMLDivElement | null}>({});
  const [expandedAnnotations, setExpandedAnnotations] = useState<string[]>([]);
  const [newAnnotation, setNewAnnotation] = useState<{
    value: string;
    explanation: string;
    annotation: string;
    allowFeedback?: boolean;
  }>({ 
    value: "", 
    explanation: "", 
    annotation: "",
    allowFeedback: false
  });
  const [showNewAnnotationForm, setShowNewAnnotationForm] = useState<{ 
    scoreName: string | null; 
    isThumbsUp: boolean; 
  }>({ scoreName: null, isThumbsUp: false });
  const [isErrorExpanded, setIsErrorExpanded] = useState(true);
  const [filterConfig, setFilterConfig] = useState<FilterConfig>([])
  const [showExpandButton, setShowExpandButton] = useState<Record<string, boolean>>({})
  const textRef = useRef<Record<string, HTMLDivElement | null>>({})
  const [thumbedUpScores, setThumbedUpScores] = useState<Set<string>>(new Set());
  const [feedbackItems, setFeedbackItems] = useState<Record<string, any[]>>({});
  const [items, setItems] = useState<Item[]>(initialItems);
  const [sampleMethod, setSampleMethod] = useState("All");
  const [sampleCount, setSampleCount] = useState(100);
  const [scoreResults, setScoreResults] = useState(sampleScoreResults);

  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }

    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)

    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  useEffect(() => {
    const truncateExplanations = () => {
      const newTruncatedExplanations: {[key: string]: string} = {};
      sampleScoreResults.forEach(section => {
        section.scores.forEach(score => {
          const element = explanationRefs.current[score.name];
          if (element) {
            const originalText = score.explanation;
            let truncatedText = originalText;
            element.textContent = truncatedText;
            
            while (element.scrollHeight > element.clientHeight && truncatedText.length > 0) {
              truncatedText = truncatedText.slice(0, -1);
              element.textContent = truncatedText + '...';
            }
            
            newTruncatedExplanations[score.name] = truncatedText + (truncatedText.length < originalText.length ? '...' : '');
          }
        });
      });
      setTruncatedExplanations(newTruncatedExplanations);
    };

    truncateExplanations();
    window.addEventListener('resize', truncateExplanations);
    return () => window.removeEventListener('resize', truncateExplanations);
  }, [sampleScoreResults]);

  useEffect(() => {
    const measureHeight = () => {
      const newShowExpandButton: Record<string, boolean> = {}
      Object.keys(textRef.current).forEach((scoreName) => {
        const element = textRef.current[scoreName]
        if (element) {
          const lineHeight = parseInt(window.getComputedStyle(element).lineHeight)
          newShowExpandButton[scoreName] = element.scrollHeight > lineHeight * 2
        }
      })
      setShowExpandButton(newShowExpandButton)
    }

    measureHeight()
    window.addEventListener('resize', measureHeight)
    return () => window.removeEventListener('resize', measureHeight)
  }, [])

  const filteredItems = useMemo(() => {
    return items.filter(item => {
      if (!selectedScorecard && filterConfig.length === 0) return true
      
      let scorecardMatch = !selectedScorecard || item.scorecard === selectedScorecard
      
      if (filterConfig.length === 0) return scorecardMatch

      return scorecardMatch && filterConfig.some(group => {
        return group.conditions.every(condition => {
          const itemValue = String(item[condition.field as keyof typeof item])
          switch (condition.operator) {
            case 'equals':
              return itemValue === condition.value
            case 'not_equals':
              return itemValue !== condition.value
            case 'contains':
              return itemValue.includes(condition.value)
            case 'not_contains':
              return !itemValue.includes(condition.value)
            case 'greater_than':
              return Number(itemValue) > Number(condition.value)
            case 'less_than':
              return Number(itemValue) < Number(condition.value)
            default:
              return true
          }
        })
      })
    })
  }, [selectedScorecard, filterConfig, items])

  const getBadgeVariant = (status: string) => {
    switch (status) {
      case 'New':
      case 'Scoring...':
        return 'bg-neutral text-primary-foreground h-6';
      case 'Done':
        return 'bg-true text-primary-foreground h-6';
      case 'Error':
        return 'bg-destructive text-destructive-foreground dark:text-primary-foreground h-6';
      default:
        return 'bg-muted text-muted-foreground h-6';
    }
  };

  const handleFilterChange = (newFilters: FilterConfig) => {
    setFilterConfig(newFilters)
  }

  const handleSampleChange = (method: string, count: number) => {
    setSampleMethod(method)
    setSampleCount(count)
    console.log(`Sampling method: ${method}, Count: ${count}`)
    // Implement the logic for applying the sampling here
  }

  const handleTimeRangeChange = (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => {
    console.log("Time range changed:", range, customRange)
    // Implement the logic for handling all default time ranges and custom date ranges
    if (range === "recent") {
      // Fetch or filter items for the recent time period
    } else if (range === "custom" && customRange) {
      // Fetch or filter items for the custom date range
    }
  }

  const ITEMS_TIME_RANGE_OPTIONS = [
    { value: "recent", label: "Recent" },
    { value: "review", label: "With Feedback" },
    { value: "custom", label: "Custom" },
  ]

  const availableFields = [
    { value: 'SelectQuote Term Life v1', label: 'SelectQuote Term Life v1' },
    { value: 'CS3 Nexstar v1', label: 'CS3 Nexstar v1' },
    { value: 'CS3 Services v2', label: 'CS3 Services v2' },
    { value: 'CS3 Audigy', label: 'CS3 Audigy' },
    { value: 'AW IB Sales', label: 'AW IB Sales' },
  ]

  const scoreOptions = [
    { value: 'Good Call', label: 'Good Call' },
    { value: 'Agent Branding', label: 'Agent Branding' },
    { value: 'Temperature Check', label: 'Temperature Check' },
    { value: 'Assumptive Close', label: 'Assumptive Close' },
  ]

  const toggleExplanation = useCallback((scoreName: string) => {
    setExpandedExplanations(prev => 
      prev.includes(scoreName) 
        ? prev.filter(name => name !== scoreName)
        : [...prev, scoreName]
    );
  }, []);

  const toggleAnnotations = useCallback((scoreName: string) => {
    setExpandedAnnotations(prev => 
      prev.includes(scoreName) 
        ? prev.filter(name => name !== scoreName)
        : [...prev, scoreName]
    );
  }, []);

  const getValueBadgeClass = (value: string) => {
    return value.toLowerCase() === 'yes' 
      ? 'bg-true text-primary-foreground w-16 justify-center' 
      : 'bg-false text-primary-foreground w-16 justify-center';
  };

  const initializeNewAnnotation = (score: any) => {
    setNewAnnotation({ 
      value: score.value, 
      explanation: score.explanation, 
      annotation: "",
      allowFeedback: score.allowFeedback // Ensure this property is set correctly
    });
  };

  const cancelAnnotation = (scoreName: string) => {
    setShowNewAnnotationForm({ scoreName: null, isThumbsUp: false });
    setNewAnnotation({ value: "", explanation: "", annotation: "", allowFeedback: false });
  };

  const setExplanationRef = useCallback((element: HTMLDivElement | null, scoreName: string) => {
    if (element) {
      explanationRefs.current[scoreName] = element;
    }
  }, []);

  const renderSelectedItem = () => {
    if (!selectedItem) return null

    const selectedItemData = items.find(item => item.id === selectedItem)
    if (!selectedItemData) return null

    return (
      <ItemDetail
        item={selectedItemData as unknown as FeedbackItem}
        getBadgeVariant={getBadgeVariant}
        getRelativeTime={getRelativeTime}
        isMetadataExpanded={isMetadataExpanded}
        setIsMetadataExpanded={setIsMetadataExpanded}
        isDataExpanded={isDataExpanded}
        setIsDataExpanded={setIsDataExpanded}
        isErrorExpanded={isErrorExpanded}
        setIsErrorExpanded={setIsErrorExpanded}
        sampleMetadata={sampleMetadata}
        sampleTranscript={sampleTranscript}
        sampleScoreResults={scoreResults}
        handleThumbsUp={handleThumbsUp}
        handleThumbsDown={handleThumbsDown}
        handleNewAnnotationSubmit={handleNewAnnotationSubmit}
        toggleAnnotations={toggleAnnotations}
        showNewAnnotationForm={showNewAnnotationForm}
        setShowNewAnnotationForm={setShowNewAnnotationForm}
        newAnnotation={newAnnotation}
        setNewAnnotation={setNewAnnotation}
        expandedAnnotations={expandedAnnotations}
        thumbedUpScores={thumbedUpScores}
        setThumbedUpScores={setThumbedUpScores}
        isFullWidth={isFullWidth}
        isFeedbackMode={false}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={() => {
          setSelectedItem(null);
          setIsFullWidth(false);
        }}
      />
    )
  }

  const handleThumbsUp = (scoreName: string) => {
    setThumbedUpScores(prev => {
      const newSet = new Set(prev);
      if (newSet.has(scoreName)) {
        newSet.delete(scoreName);
      } else {
        newSet.add(scoreName);
      }
      return newSet;
    });

    toggleNewAnnotationForm(scoreName, true);
  };

  const handleThumbsDown = (scoreName: string) => {
    setThumbedUpScores(prev => {
      const newSet = new Set(prev);
      newSet.delete(scoreName);
      return newSet;
    });
    toggleNewAnnotationForm(scoreName, false);
  };

  const toggleNewAnnotationForm = (scoreName: string, isThumbsUp: boolean) => {
    if (showNewAnnotationForm.scoreName === scoreName && 
        showNewAnnotationForm.isThumbsUp === isThumbsUp) {
      setShowNewAnnotationForm({ scoreName: null, isThumbsUp: false });
    } else {
      setShowNewAnnotationForm({ scoreName, isThumbsUp });
      const foundScore = sampleScoreResults
        .flatMap(section => section.scores)
        .find(score => score.name === scoreName);
      
      if (foundScore) {
        initializeNewAnnotation(foundScore);
      } else {
        console.warn(`No score found with name: ${scoreName}`);
        setNewAnnotation({ value: "", explanation: "", annotation: "", allowFeedback: false });
      }
    }
  };

  const handleNewAnnotationSubmit = (scoreName: string) => {
    // Create the new annotation
    const newAnnotationItem = {
      value: newAnnotation.value,
      explanation: newAnnotation.explanation,
      annotation: newAnnotation.annotation,
      timestamp: new Date().toISOString(),
      user: {
        name: "Ryan Porter",
        initials: "RP"
      },
      isThumbsUp: showNewAnnotationForm.isThumbsUp
    };

    // Update the score results state
    setScoreResults(prevResults => 
      prevResults.map(section => ({
        ...section,
        scores: section.scores.map(score => 
          score.name === scoreName 
            ? { 
                ...score, 
                isAnnotated: true, 
                annotations: [...(score.annotations || []), newAnnotationItem] 
              }
            : score
        )
      }))
    );

    // Close the form
    setShowNewAnnotationForm({ scoreName: null, isThumbsUp: false });
    
    // Clear the form data
    setNewAnnotation({ value: "", explanation: "", annotation: "", allowFeedback: false });
    
    // Expand the feedback history
    setExpandedAnnotations(prev => 
      prev.includes(scoreName) ? prev : [...prev, scoreName]
    );
  };

  function renderScoreResult(score: any, isAnnotation = false) {
    const hasAnnotations = score.annotations && score.annotations.length > 0;
    const isThumbedUp = isAnnotation ? score.isThumbsUp : thumbedUpScores.has(score.name);

    const getBorderColor = () => {
      if (score.isSystem) return 'var(--secondary)';
      if (isThumbedUp) return 'var(--true)';
      return 'var(--false)';
    };

    const hasFeedback = score.isAnnotated || hasAnnotations;
    const hasThumbsDownFeedback = (score.annotations || [])
      .some((annotation: Annotation) => !annotation.isThumbsUp);
    const feedbackIconColor = hasFeedback
      ? hasThumbsDownFeedback
        ? 'bg-false text-primary-foreground hover:bg-false hover:text-primary-foreground'
        : 'bg-true text-primary-foreground hover:bg-true hover:text-primary-foreground'
      : '';

    return (
      <div 
        className={`py-2 ${isAnnotation ? 'pl-4 border-l-4' : ''} relative`}
        style={isAnnotation ? { borderColor: getBorderColor() + ' !important' } : {}}
      >
        {isAnnotation && !score.isSystem && (
          <div className="absolute top-2 left-4 rounded-full p-1" 
               style={{ backgroundColor: score.isThumbsUp ? 'var(--true)' : 'var(--false)' }}>
            {score.isThumbsUp ? (
              <ThumbsUp className="h-3 w-3 text-primary-foreground" />
            ) : (
              <ThumbsDown className="h-3 w-3 text-primary-foreground" />
            )}
          </div>
        )}
        {isAnnotation ? (
          <>
            <div className="flex justify-end mb-2">
              <Badge className={getValueBadgeClass(score.value)}>{score.value}</Badge>
            </div>
            <div className="relative">
              <div 
                ref={(el) => {
                  if (el) {
                    textRef.current[score.name] = el;
                  }
                }}
                className="text-sm text-muted-foreground overflow-hidden cursor-pointer"
                style={{ 
                  display: '-webkit-box',
                  WebkitLineClamp: '2',
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  ...(expandedExplanations.includes(score.name) ? 
                      { WebkitLineClamp: 'unset', display: 'block' } : {})
                }}
                onClick={() => toggleExplanation(score.name)}
              >
                {renderRichText(score.explanation)}
              </div>
              {showExpandButton[score.name] && (
                <Button 
                  variant="link" 
                  size="sm" 
                  onClick={() => toggleExplanation(score.name)}
                  className="absolute bottom-0 right-0 px-0 py-1 h-auto bg-white dark:bg-gray-800"
                >
                  {expandedExplanations.includes(score.name) 
                    ? <ChevronUp className="h-3 w-3 inline ml-1" />
                    : <ChevronDown className="h-3 w-3 inline ml-1" />
                  }
                </Button>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="flex justify-between items-center mb-1">
              <div className="flex items-center">
                <h5 className="text-sm font-medium">{score.name}</h5>
                <div className="inline-flex items-center ml-1">
                  <Link href={`/scorecards?score=${encodeURIComponent(score.name)}`} passHref>
                    <Button variant="ghost" size="sm" className="p-0 h-auto translate-y-[2px]" 
                           title={`More info about ${score.name}`}>
                      <Info className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </Link>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {hasFeedback && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleAnnotations(score.name)}
                    className={`text-xs ${feedbackIconColor}`}
                  >
                    <MessageCircleMore className="h-4 w-4" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleThumbsUp(score.name)}
                  className="text-xs hover:bg-true hover:text-primary-foreground"
                >
                  <ThumbsUp className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleThumbsDown(score.name)}
                  className="text-xs hover:bg-false hover:text-primary-foreground"
                >
                  <ThumbsDown className="h-4 w-4" />
                </Button>
                <Badge className={getValueBadgeClass(score.value)}>{score.value}</Badge>
              </div>
            </div>
            {/* Rest of the non-annotation rendering code... */}
          </>
        )}
        {/* Rest of the function remains the same... */}
      </div>
    );
  }

  const handleItemClick = (itemId: number) => {
    setSelectedItem(itemId)
    if (isNarrowViewport) {
      setIsFullWidth(true)
    }
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex flex-wrap justify-between items-start gap-4">
        <div className="flex-shrink-0">
          <ScorecardContext 
            selectedScorecard={selectedScorecard}
            setSelectedScorecard={setSelectedScorecard}
            selectedScore={selectedScore}
            setSelectedScore={setSelectedScore}
            availableFields={availableFields}
            timeRangeOptions={scoreOptions}
          />
        </div>
        <div className="flex-shrink-0 ml-auto">
          <ItemContext
            handleFilterChange={handleFilterChange}
            handleSampleChange={handleSampleChange}
            handleTimeRangeChange={handleTimeRangeChange}
            availableFields={availableFields}
            timeRangeOptions={ITEMS_TIME_RANGE_OPTIONS}
          />
        </div>
      </div>

      <div className="flex-grow flex flex-col overflow-hidden pb-2">
        {selectedItem && (isNarrowViewport || isFullWidth) ? (
          <div className="flex-grow overflow-hidden">
            {renderSelectedItem()}
          </div>
        ) : (
          <div className={`flex ${isNarrowViewport ? 'flex-col' : 'space-x-6'} h-full`}>
            <div className={`${isFullWidth ? 'hidden' : 'flex-1'} @container overflow-auto`}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[40%]">Item</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Inferences</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Results</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Cost</TableHead>
                    <TableHead className="w-[15%] @[630px]:table-cell hidden text-right">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredItems.map((item) => (
                    <TableRow 
                      key={item.id} 
                      onClick={() => handleItemClick(item.id)} 
                      className="cursor-pointer transition-colors duration-200 hover:bg-muted"
                    >
                      <TableCell className="font-medium pr-4">
                        <div>
                          {/* Narrow variant - visible below 630px */}
                          <div className="block @[630px]:hidden">
                            <div className="flex justify-between items-start mb-2">
                              <div className="font-semibold">{item.scorecard}</div>
                              <Badge 
                                className={`w-24 justify-center ${getBadgeVariant(item.status)}`}
                              >
                                {item.status}
                              </Badge>
                            </div>
                            <div className="text-sm text-muted-foreground mb-2">
                              {formatTimeAgo(item.date, true)}
                            </div>
                            <div className="flex justify-between items-end">
                              <div className="text-sm text-muted-foreground">
                                {item.inferences} inferences<br />
                                {item.results} results
                              </div>
                              <div className="font-semibold">{item.cost}</div>
                            </div>
                          </div>
                          {/* Wide variant - visible at 630px and above */}
                          <div className="hidden @[630px]:block">
                            {item.scorecard}
                            <div className="text-sm text-muted-foreground">
                              {formatTimeAgo(item.date)}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-right">{item.inferences}</TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-right">{item.results}</TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-right">{item.cost}</TableCell>
                      <TableCell className="hidden @[630px]:table-cell text-right">
                        <Badge 
                          className={`w-24 justify-center ${getBadgeVariant(item.status)}`}
                        >
                          {item.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
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

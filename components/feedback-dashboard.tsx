"use client"

import React, { useState, useMemo, useEffect, useRef, useCallback } from "react"
import { useRouter, useSearchParams } from 'next/navigation'
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, ChevronLeft } from "lucide-react"
import { formatDistanceToNow, parseISO } from "date-fns"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Progress } from "@/components/ui/progress"
import { TimeRangeSelector } from "@/components/time-range-selector"
import ReactMarkdown from 'react-markdown'
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import Link from 'next/link'
import { FilterControl, FilterConfig } from "@/components/filter-control"
import ItemDetail from './ItemDetail'

// Add this type definition
type TimeRangeOption = {
  value: string;
  label: string;
};

// Get the current date and time
const now = new Date();

// Function to create a date relative to now
const relativeDate = (days: number, hours: number, minutes: number) => {
  const date = new Date(now);
  date.setDate(date.getDate() - days);
  date.setHours(date.getHours() - hours, date.getMinutes() - minutes);
  return date.toISOString();
};

const sampleScoreResults = [
  {
    section: "Compliance",
    scores: [
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
    ]
  }
];

// Define score counts for each scorecard
const scorecardScoreCounts = {
  "CS3 Services v2": 1,
  "CS3 Audigy": 4,
  "AW IB Sales": 1,
  "CS3 Nexstar v1": 29,
  "SelectQuote Term Life v1": 42,
};

// First, let's define an interface for the feedback item
interface FeedbackItem {
  id: number;
  scorecard: string;
  score: number;
  date: string;
  status: string;
  hasFeedback: boolean;
  scoreCount: number;
  scoreResults?: typeof sampleScoreResults;  // Make this optional
  metadata?: Array<{ key: string; value: string }>;  // Add this line
  lastUpdated: string;
}

// First, let's create a function to generate score results based on the item's status
const getScoreResults = (status: string) => {
  if (status === "New" || status === "In Review") {
    return [
      {
        section: "Compliance",
        scores: [
          { 
            name: "Profanity", 
            value: "No", 
            explanation: "No profanity was detected during the call. Both the agent and the customer maintained professional and respectful language throughout the entire conversation.",
            isAnnotated: false,
            annotations: []
          },
        ]
      }
    ];
  } else {
    return sampleScoreResults;
  }
};

// Now, let's update the initialFeedbackItems declaration
const initialFeedbackItems: FeedbackItem[] = [
  { id: 30, scorecard: "CS3 Services v2", score: 80, date: relativeDate(0, 0, 5), status: "New", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Services v2"], lastUpdated: "", scoreResults: getScoreResults("New") },
  { id: 29, scorecard: "CS3 Audigy", score: 89, date: relativeDate(0, 0, 15), status: "New", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Audigy"], lastUpdated: "", scoreResults: getScoreResults("New") },
  { id: 28, scorecard: "AW IB Sales", score: 96, date: relativeDate(0, 0, 30), status: "New", hasFeedback: false, scoreCount: scorecardScoreCounts["AW IB Sales"], lastUpdated: "", scoreResults: getScoreResults("New") },
  { id: 27, scorecard: "CS3 Nexstar v1", score: 88, date: relativeDate(0, 1, 0), status: "In Review...", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"], lastUpdated: relativeDate(0, 0, 0), scoreResults: getScoreResults("In Review...") },
  { id: 26, scorecard: "SelectQuote Term Life v1", score: 83, date: relativeDate(0, 1, 30), status: "In Review...", hasFeedback: false, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"], lastUpdated: relativeDate(0, 1, 0), scoreResults: getScoreResults("In Review...") },
  { id: 25, scorecard: "AW IB Sales", score: 94, date: relativeDate(0, 2, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["AW IB Sales"], lastUpdated: relativeDate(0, 1, 30), scoreResults: getScoreResults("Done") },
  { id: 24, scorecard: "CS3 Audigy", score: 86, date: relativeDate(0, 3, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Audigy"], lastUpdated: relativeDate(0, 2, 30), scoreResults: getScoreResults("Done") },
  { id: 23, scorecard: "CS3 Services v2", score: 79, date: relativeDate(0, 4, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Services v2"], lastUpdated: relativeDate(0, 3, 30), scoreResults: getScoreResults("Done") },
  { id: 22, scorecard: "CS3 Nexstar v1", score: 91, date: relativeDate(0, 5, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"], lastUpdated: relativeDate(0, 4, 30), scoreResults: getScoreResults("Done") },
  { id: 21, scorecard: "SelectQuote Term Life v1", score: 89, date: relativeDate(0, 6, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"], lastUpdated: relativeDate(0, 5, 30), scoreResults: getScoreResults("Done") },
  { id: 20, scorecard: "CS3 Services v2", score: 82, date: relativeDate(1, 0, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Services v2"], lastUpdated: relativeDate(0, 23, 30), scoreResults: getScoreResults("Done") },
  { id: 19, scorecard: "AW IB Sales", score: 93, date: relativeDate(1, 2, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["AW IB Sales"], lastUpdated: relativeDate(1, 1, 30), scoreResults: getScoreResults("Done") },
  { id: 18, scorecard: "CS3 Audigy", score: 87, date: relativeDate(1, 4, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Audigy"], lastUpdated: relativeDate(1, 3, 30), scoreResults: getScoreResults("Done") },
  { id: 17, scorecard: "SelectQuote Term Life v1", score: 85, date: relativeDate(1, 6, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"], lastUpdated: relativeDate(1, 5, 30), scoreResults: getScoreResults("Done") },
  { id: 16, scorecard: "CS3 Nexstar v1", score: 90, date: relativeDate(1, 8, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"], lastUpdated: relativeDate(1, 7, 30), scoreResults: getScoreResults("Done") },
  { id: 15, scorecard: "CS3 Services v2", score: 81, date: relativeDate(1, 10, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Services v2"], lastUpdated: relativeDate(1, 9, 30), scoreResults: getScoreResults("Done") },
  { id: 14, scorecard: "AW IB Sales", score: 95, date: relativeDate(1, 12, 0), status: "Done", hasFeedback: false, scoreCount: scorecardScoreCounts["AW IB Sales"], lastUpdated: relativeDate(1, 11, 30), scoreResults: getScoreResults("Done") },
  { id: 13, scorecard: "CS3 Audigy", score: 88, date: relativeDate(1, 14, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Audigy"], lastUpdated: relativeDate(1, 13, 30), scoreResults: getScoreResults("Done") },
  { id: 12, scorecard: "SelectQuote Term Life v1", score: 84, date: relativeDate(1, 16, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"], lastUpdated: relativeDate(1, 15, 30), scoreResults: getScoreResults("Done") },
  { id: 11, scorecard: "CS3 Nexstar v1", score: 92, date: relativeDate(1, 18, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"], lastUpdated: relativeDate(1, 17, 30), scoreResults: getScoreResults("Done") },
  { id: 10, scorecard: "CS3 Services v2", score: 83, date: relativeDate(1, 20, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Services v2"], lastUpdated: relativeDate(1, 19, 30), scoreResults: getScoreResults("Done") },
  { id: 9, scorecard: "AW IB Sales", score: 97, date: relativeDate(1, 22, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["AW IB Sales"], lastUpdated: relativeDate(1, 21, 30), scoreResults: getScoreResults("Done") },
  { id: 8, scorecard: "CS3 Audigy", score: 89, date: relativeDate(2, 0, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Audigy"], lastUpdated: relativeDate(1, 23, 30), scoreResults: getScoreResults("Done") },
  { id: 7, scorecard: "SelectQuote Term Life v1", score: 86, date: relativeDate(2, 2, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"], lastUpdated: relativeDate(2, 1, 30), scoreResults: getScoreResults("Done") },
  { id: 6, scorecard: "CS3 Nexstar v1", score: 93, date: relativeDate(2, 4, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"], lastUpdated: relativeDate(2, 3, 30), scoreResults: getScoreResults("Done") },
  { id: 5, scorecard: "CS3 Services v2", score: 84, date: relativeDate(2, 6, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Services v2"], lastUpdated: relativeDate(2, 5, 30), scoreResults: getScoreResults("Done") },
  { id: 4, scorecard: "AW IB Sales", score: 98, date: relativeDate(2, 8, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["AW IB Sales"], lastUpdated: relativeDate(2, 7, 30), scoreResults: getScoreResults("Done") },
  { id: 3, scorecard: "CS3 Audigy", score: 90, date: relativeDate(2, 10, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Audigy"], lastUpdated: relativeDate(2, 9, 30), scoreResults: getScoreResults("Done") },
  { id: 2, scorecard: "SelectQuote Term Life v1", score: 87, date: relativeDate(2, 12, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"], lastUpdated: relativeDate(2, 11, 30), scoreResults: getScoreResults("Done") },
  { id: 1, scorecard: "CS3 Nexstar v1", score: 94, date: relativeDate(2, 14, 0), status: "Done", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"], lastUpdated: relativeDate(2, 13, 30), scoreResults: getScoreResults("Done") },
];

// Sort items by date, newest first
initialFeedbackItems.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

const FEEDBACK_TIME_RANGE_OPTIONS: TimeRangeOption[] = [
  { value: "recent", label: "Recent" },
  { value: "review", label: "With Feedback" },
  { value: "custom", label: "Custom" },
]

// Add this interface near the top of your file, with other type definitions
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
  isThumbsUp: boolean; // Add this new field
}

interface QueueData {
  id: number;
  name: string;
  scores: number;
  items: number;
  date: string;
  started: string;
  progress: number;
  processedItems: number;
  totalItems: number;
  elapsedTime: string;
  estimatedTimeRemaining: string;
}

// Add this near the top of the file, with other sample data
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
];

export default function FeedbackDashboard() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const queueId = searchParams.get('queue')
  const [selectedItem, setSelectedItem] = useState<number | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [filterConfig, setFilterConfig] = useState<FilterConfig>([])
  const [expandedExplanations, setExpandedExplanations] = useState<string[]>([]);
  const [truncatedExplanations, setTruncatedExplanations] = useState<{[key: string]: string}>({});
  const explanationRefs = useRef<{[key: string]: HTMLDivElement | null}>({});
  const [isMetadataExpanded, setIsMetadataExpanded] = useState(false)
  const [isDataExpanded, setIsDataExpanded] = useState(false)
  const [showExpandButton, setShowExpandButton] = useState<Record<string, boolean>>({})
  const textRef = useRef<Record<string, HTMLDivElement | null>>({})
  const [expandedAnnotations, setExpandedAnnotations] = useState<string[]>([]);
  const [newAnnotation, setNewAnnotation] = useState({ value: "", explanation: "", annotation: "" });
  const [showNewAnnotationForm, setShowNewAnnotationForm] = useState<{ scoreName: string | null, isThumbsUp: boolean }>({ scoreName: null, isThumbsUp: false });
  const [thumbedUpScores, setThumbedUpScores] = useState<Set<string>>(new Set());
  const [feedbackItems, setFeedbackItems] = useState<FeedbackItem[]>(initialFeedbackItems);
  const [isDataExpandedDefault, setIsDataExpandedDefault] = useState(false);
  const [isErrorExpanded, setIsErrorExpanded] = useState(true);
  const [sampleMetadata] = useState([
    { key: "Duration", value: "1022" },
    { key: "Dual Channel", value: "true" },
    { key: "Agent Name", value: "Johnny Appleseed" },
    { key: "Customer ID", value: "CUS-12345" },
    { key: "Call Type", value: "Inbound" },
    { key: "Department", value: "Customer Service" },
    { key: "Language", value: "English" },
    { key: "Recording ID", value: "REC-67890" },
  ]);
  const [scoreResults, setScoreResults] = useState(sampleScoreResults);

  // Simulated queue data (replace with actual data fetching logic)
  const queueData: QueueData = useMemo(() => {
    // This should be replaced with actual data fetching based on queueId
    return {
      id: Number(queueId),
      name: "CS3 Services v2",
      scores: 1,
      items: 150,
      date: new Date().toISOString(),
      started: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
      progress: 75,
      processedItems: 112,
      totalItems: 150,
      elapsedTime: "00:45:30",
      estimatedTimeRemaining: "00:15:00"
    }
  }, [queueId])

  useEffect(() => {
    const checkViewportWidth = () => {
      const isNarrow = window.innerWidth < 640;
      setIsNarrowViewport(isNarrow);
      setIsDataExpandedDefault(!isNarrow && isFullWidth);
    }

    checkViewportWidth();
    window.addEventListener('resize', checkViewportWidth);

    return () => window.removeEventListener('resize', checkViewportWidth);
  }, [isFullWidth]);

  useEffect(() => {
    setIsDataExpanded(isDataExpandedDefault);
  }, [isDataExpandedDefault]);

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
    return feedbackItems.filter(item => {
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
  }, [selectedScorecard, filterConfig, feedbackItems])

  const getRelativeTime = (dateString: string | undefined) => {
    if (!dateString) return 'Unknown date';
    const date = parseISO(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  };

  const handleItemClick = (itemId: number) => {
    setSelectedItem(itemId)
    if (isNarrowViewport) {
      setIsFullWidth(true)
    }
  }

  const getBadgeVariant = (status: string) => {
    switch (status) {
      case 'New':
        return 'bg-neutral text-primary-foreground h-6 w-24 justify-center';
      case 'In Review...':
        return 'bg-primary text-primary-foreground h-6 w-24 justify-center';
      case 'Done':
        return 'bg-true text-primary-foreground h-6 w-24 justify-center';
      default:
        return 'bg-muted text-muted-foreground h-6 w-24 justify-center';
    }
  };

  const handleTimeRangeChange = (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => {
    console.log("Time range changed:", range, customRange)
    // Implement the logic for handling "recent" and custom date ranges
  }

  const handleFilterChange = (newFilters: FilterConfig) => {
    setFilterConfig(newFilters)
  }

  const availableFields = [
    { value: 'scorecard', label: 'Scorecard' },
    { value: 'score', label: 'Score' },
    { value: 'status', label: 'Status' },
    { value: 'results', label: 'Results' },
    { value: 'inferences', label: 'Inferences' },
    { value: 'cost', label: 'Cost' },
    { value: 'feedback', label: 'Feedback' },
  ]

  const getValueBadgeClass = (value: string) => {
    return value.toLowerCase() === 'yes' 
      ? 'bg-true text-primary-foreground w-16 justify-center' 
      : 'bg-false text-primary-foreground w-16 justify-center';
  };

  const setExplanationRef = useCallback((element: HTMLDivElement | null, scoreName: string) => {
    if (element) {
      explanationRefs.current[scoreName] = element;
    }
  }, []);

  const toggleExplanation = useCallback((scoreName: string) => {
    setExpandedExplanations(prev => 
      prev.includes(scoreName) 
        ? prev.filter(name => name !== scoreName)
        : [...prev, scoreName]
    );
  }, []);

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

  const toggleAnnotations = useCallback((scoreName: string) => {
    setExpandedAnnotations(prev => 
      prev.includes(scoreName) 
        ? prev.filter(name => name !== scoreName)
        : [...prev, scoreName]
    );
  }, []);

  const initializeNewAnnotation = (score: any) => {
    setNewAnnotation({ 
      value: score.value, 
      explanation: score.explanation, 
      annotation: "" 
    });
  };

  const cancelAnnotation = (scoreName: string) => {
    setShowNewAnnotationForm({ scoreName: null, isThumbsUp: false });
    setNewAnnotation({ value: "", explanation: "", annotation: "" });
  };

  const handleNewAnnotationSubmit = (scoreName: string) => {
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

    setFeedbackItems(prevItems => {
      return prevItems.map(item => {
        if (item.id === selectedItem) {
          const updatedScoreResults = item.scoreResults?.map(section => ({
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
          }));
          return {
            ...item,
            scoreResults: updatedScoreResults,
            hasFeedback: true
          };
        }
        return item;
      });
    });

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

    setShowNewAnnotationForm({ scoreName: null, isThumbsUp: false });
    setNewAnnotation({ value: "", explanation: "", annotation: "" });
    setExpandedAnnotations(prev => 
      prev.includes(scoreName) ? prev : [...prev, scoreName]
    );
  };

  const toggleNewAnnotationForm = (scoreName: string, isThumbsUp: boolean) => {
    if (showNewAnnotationForm.scoreName === scoreName && showNewAnnotationForm.isThumbsUp === isThumbsUp) {
      setShowNewAnnotationForm({ scoreName: null, isThumbsUp: false });
    } else {
      setShowNewAnnotationForm({ scoreName, isThumbsUp });
      const foundScore = feedbackItems
        .flatMap(item => item.scoreResults?.flatMap(section => section.scores) ?? [])
        .find(score => score?.name === scoreName);
      
      if (foundScore) {
        initializeNewAnnotation(foundScore);
      } else {
        console.warn(`No score found with name: ${scoreName}`);
        setNewAnnotation({ value: "", explanation: "", annotation: "" });
      }
    }
  };

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

  const renderSelectedItem = () => {
    if (!selectedItem) return null;

    const selectedItemData = feedbackItems.find(item => item.id === selectedItem);
    if (!selectedItemData) return null;

    const DetailViewControlButtons = (
      <>
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
      </>
    );

    return (
      <ItemDetail
        item={selectedItemData}
        controlButtons={DetailViewControlButtons}
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
        newAnnotation={newAnnotation}
        setNewAnnotation={setNewAnnotation}
        expandedAnnotations={expandedAnnotations}
        thumbedUpScores={thumbedUpScores}
        setShowNewAnnotationForm={setShowNewAnnotationForm}
        setThumbedUpScores={setThumbedUpScores}
        isFullWidth={isFullWidth}
        isFeedbackMode={true}
      />
    );
  };

  const getFeedbackBadgeClass = (hasFeedback: boolean) => {
    return hasFeedback
      ? 'bg-true text-primary-foreground w-16 justify-center'
      : 'bg-false text-primary-foreground w-16 justify-center';
  };

  const handleCloseQueue = () => {
    router.push('/feedback-queues')
  }

  const renderQueueSummary = () => (
    <div className="mb-6">
      <div className="mb-4">
        <h2 className="text-2xl font-semibold">{queueData.name}</h2>
        <p className="text-sm text-muted-foreground">
          Started {formatDistanceToNow(parseISO(queueData.started), { addSuffix: true })}
        </p>
      </div>
      <div className="flex items-center justify-between">
        <div className="w-1/4">
          <p className="text-sm font-medium text-muted-foreground">Scores</p>
          <p>{queueData.scores}</p>
        </div>
        <div className="w-1/4">
          <p className="text-sm font-medium text-muted-foreground">Last Updated</p>
          <p>{formatDistanceToNow(parseISO(queueData.date), { addSuffix: true })}</p>
        </div>
        <div className="w-1/2">
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <div className="font-semibold">Progress: {queueData.progress}%</div>
              <div>Elapsed Time: {queueData.elapsedTime}</div>
            </div>
            <div className="relative w-full h-6 bg-neutral rounded-full">
              <div
                className="absolute top-0 left-0 h-full bg-primary flex items-center pl-2 text-xs text-primary-foreground font-medium rounded-full"
                style={{ width: `${queueData.progress}%` }}
              >
                {queueData.progress}%
              </div>
            </div>
            <div className="flex justify-between text-xs">
              <div>{queueData.processedItems}/{queueData.totalItems}</div>
              <div>ETA: {queueData.estimatedTimeRemaining}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )

  function renderScoreResult(score: any, isAnnotation = false) {
    const hasAnnotations = score.annotations && score.annotations.length > 0;
    const isThumbedUp = isAnnotation ? score.isThumbsUp : thumbedUpScores.has(score.name);

    const getBorderColor = () => {
      if (score.isSystem) return 'var(--secondary)';
      if (isThumbedUp) return 'var(--true)';
      return 'var(--false)';
    };

    const hasFeedback = score.isAnnotated || hasAnnotations;
    const hasThumbsDownFeedback = (score.annotations || []).some((annotation: Annotation) => !annotation.isThumbsUp);
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
                  ...(expandedExplanations.includes(score.name) ? { WebkitLineClamp: 'unset', display: 'block' } : {})
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
                    <Button variant="ghost" size="sm" className="p-0 h-auto translate-y-[2px]" title={`More info about ${score.name}`}>
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
                  ...(expandedExplanations.includes(score.name) ? { WebkitLineClamp: 'unset', display: 'block' } : {})
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
        )}
        {isAnnotation && (
          <div className="flex justify-between items-center mt-2 text-xs text-muted-foreground">
            <span>{new Date(score.timestamp).toLocaleString()}</span>
            {score.user && (
              <div className="flex items-center space-x-2">
                <span>{score.user.name}</span>
                <Avatar className="h-6 w-6 bg-muted">
                  <AvatarFallback className="bg-muted">{score.user.initials}</AvatarFallback>
                </Avatar>
              </div>
            )}
          </div>
        )}
        {score.annotation && (
          <div className="mt-2 text-sm italic">
            "{score.annotation}"
          </div>
        )}
        {!isAnnotation && (
          <>
            {(showNewAnnotationForm.scoreName === score.name) && (
              <div 
                className="mb-2 space-y-2 border-l-4 pl-4"
                style={{ borderColor: (showNewAnnotationForm.isThumbsUp ? 'var(--true)' : 'var(--false)') + ' !important' }}
              >
                <div className="mb-4">
                  <h6 className="text-sm font-medium mb-2">Feedback</h6>
                  <div className="space-y-2">
                    {showNewAnnotationForm.isThumbsUp ? (
                      <>
                        <div className="text-sm font-medium">Value: {newAnnotation.value}</div>
                        <div className="text-sm">Explanation: {newAnnotation.explanation}</div>
                      </>
                    ) : (
                      <>
                        <Select 
                          onValueChange={(value) => setNewAnnotation({...newAnnotation, value})}
                          value={newAnnotation.value}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select value" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="Yes">Yes</SelectItem>
                            <SelectItem value="No">No</SelectItem>
                          </SelectContent>
                        </Select>
                        <Textarea 
                          placeholder="Explanation" 
                          value={newAnnotation.explanation}
                          onChange={(e) => setNewAnnotation({...newAnnotation, explanation: e.target.value})}
                        />
                      </>
                    )}
                    <Input 
                      placeholder="Feedback" 
                      value={newAnnotation.annotation}
                      onChange={(e) => setNewAnnotation({...newAnnotation, annotation: e.target.value})}
                    />
                    <div className="flex justify-end space-x-2">
                      <Button variant="outline" onClick={() => setShowNewAnnotationForm({ scoreName: null, isThumbsUp: false })}>Cancel</Button>
                      <Button onClick={() => handleNewAnnotationSubmit(score.name)}>Submit Feedback</Button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {(score.isAnnotated || hasAnnotations) && expandedAnnotations.includes(score.name) && (
              <div className="mt-2 space-y-2">
                <div className="flex justify-between items-center mb-2">
                  <h6 className="text-sm font-medium">Feedback</h6>
                </div>
                {(score.annotations || [])
                  .sort((a: Annotation, b: Annotation) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
                  .map((annotation: Annotation, annotationIndex: number) => (
                    <div key={annotationIndex} className="relative">
                      {renderScoreResult({...annotation, isAnnotated: true}, true)}
                    </div>
                  ))}
              </div>
            )}
          </>
        )}
      </div>
    )
  }

  return (
    <div className="h-full flex">
      {/* Left panel - only show when not full width */}
      {!isFullWidth && (
        <div className={`${selectedItem && !isNarrowViewport ? 'w-1/2' : 'w-full'} h-full overflow-auto p-4`}>
          {renderQueueSummary()}

          <div className="mb-8">
            <h3 className="text-xl font-semibold mb-2">Instructions</h3>
            <p className="text-base text-muted-foreground mb-4">
              Please review these examples we found that might demonstrate problems with the alignment 
              of our profanity standards. Please pay close attention to words that we're flagging for 
              profanity that are not really profanity by the client's standards.
            </p>
          </div>

          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-semibold">{queueData.items} Items</h3>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]">Item</TableHead>
                <TableHead className="w-[30%] @[630px]:table-cell hidden">Last Updated</TableHead>
                <TableHead className="w-[30%] @[630px]:table-cell hidden text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {feedbackItems.map((item) => (
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
                          <div className="text-sm text-muted-foreground">{getRelativeTime(item.date)}</div>
                          <Badge 
                            className={getBadgeVariant(item.status)}
                          >
                            {item.status}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground mt-1">
                          Last Updated: {item.lastUpdated ? getRelativeTime(item.lastUpdated) : '-'}
                        </div>
                      </div>
                      {/* Wide variant - visible at 630px and above */}
                      <div className="hidden @[630px]:block">
                        <div className="text-sm text-muted-foreground">{getRelativeTime(item.date)}</div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden @[630px]:table-cell">
                    {item.lastUpdated ? getRelativeTime(item.lastUpdated) : '-'}
                  </TableCell>
                  <TableCell className="hidden @[630px]:table-cell text-right">
                    <Badge 
                      className={getBadgeVariant(item.status)}
                    >
                      {item.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Right panel - item detail */}
      {selectedItem && !isNarrowViewport && (
        <div className={`${isFullWidth ? 'w-full' : 'w-1/2'} h-full overflow-auto`}>
          {renderSelectedItem()}
        </div>
      )}

      {/* Mobile view - full screen item detail */}
      {selectedItem && isNarrowViewport && (
        <div className="fixed inset-0 bg-background z-50">
          {renderSelectedItem()}
        </div>
      )}
    </div>
  )
}

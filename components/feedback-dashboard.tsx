"use client"

import React from "react"
import { useState, useMemo, useEffect, useRef, useCallback } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown } from "lucide-react"
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
import { TimeRangeSelector, TimeRangeOption } from "@/components/time-range-selector"
import ReactMarkdown from 'react-markdown'
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import Link from 'next/link'
import { FilterControl, FilterConfig } from "@/components/filter-control"

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
    section: "Technical",
    scores: [
      { name: "Scoreable Call", value: "Yes", explanation: "The call meets all criteria to be scored. This includes having clear audio, being of sufficient length, and containing relevant content for evaluation." },
      { name: "Call Efficiency", value: "Yes", explanation: "The agent managed the call time effectively while still addressing the customer's needs." },
    ]
  },
  {
    section: "Customer Service",
    scores: [
      { name: "Rapport", value: "Yes", explanation: "The agent demonstrated excellent rapport-building skills throughout the call." },
      { name: "Problem Resolution", value: "Yes", explanation: "The agent effectively resolved the customer's issue." },
    ]
  },
  {
    section: "Compliance",
    scores: [
      { name: "DNC Requested", value: "No", explanation: "The customer did not request to be added to the Do Not Call list." },
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

const initialFeedbackItems = [
  { id: 30, scorecard: "CS3 Services v2", score: 80, date: relativeDate(0, 0, 5), status: "new", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Services v2"] },
  { id: 29, scorecard: "CS3 Audigy", score: 89, date: relativeDate(0, 0, 15), status: "new", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Audigy"] },
  { id: 28, scorecard: "AW IB Sales", score: 96, date: relativeDate(0, 0, 30), status: "new", hasFeedback: false, scoreCount: scorecardScoreCounts["AW IB Sales"] },
  { id: 27, scorecard: "CS3 Nexstar v1", score: 88, date: relativeDate(0, 1, 0), status: "error", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"] },
  { id: 26, scorecard: "SelectQuote Term Life v1", score: 83, date: relativeDate(0, 1, 30), status: "scoring...", hasFeedback: false, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"] },
  { id: 25, scorecard: "AW IB Sales", score: 94, date: relativeDate(0, 2, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["AW IB Sales"] },
  { id: 24, scorecard: "CS3 Audigy", score: 86, date: relativeDate(0, 3, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Audigy"] },
  { id: 23, scorecard: "CS3 Services v2", score: 79, date: relativeDate(0, 4, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Services v2"] },
  { id: 22, scorecard: "CS3 Nexstar v1", score: 91, date: relativeDate(0, 5, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"] },
  { id: 21, scorecard: "SelectQuote Term Life v1", score: 89, date: relativeDate(0, 6, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"] },
  { id: 20, scorecard: "CS3 Services v2", score: 82, date: relativeDate(1, 0, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Services v2"] },
  { id: 19, scorecard: "AW IB Sales", score: 93, date: relativeDate(1, 2, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["AW IB Sales"] },
  { id: 18, scorecard: "CS3 Audigy", score: 87, date: relativeDate(1, 4, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Audigy"] },
  { id: 17, scorecard: "SelectQuote Term Life v1", score: 85, date: relativeDate(1, 6, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"] },
  { id: 16, scorecard: "CS3 Nexstar v1", score: 90, date: relativeDate(1, 8, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"] },
  { id: 15, scorecard: "CS3 Services v2", score: 81, date: relativeDate(1, 10, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["CS3 Services v2"] },
  { id: 14, scorecard: "AW IB Sales", score: 95, date: relativeDate(1, 12, 0), status: "scored", hasFeedback: false, scoreCount: scorecardScoreCounts["AW IB Sales"] },
  { id: 13, scorecard: "CS3 Audigy", score: 88, date: relativeDate(1, 14, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Audigy"] },
  { id: 12, scorecard: "SelectQuote Term Life v1", score: 84, date: relativeDate(1, 16, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"] },
  { id: 11, scorecard: "CS3 Nexstar v1", score: 92, date: relativeDate(1, 18, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"] },
  { id: 10, scorecard: "CS3 Services v2", score: 83, date: relativeDate(1, 20, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Services v2"] },
  { id: 9, scorecard: "AW IB Sales", score: 97, date: relativeDate(1, 22, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["AW IB Sales"] },
  { id: 8, scorecard: "CS3 Audigy", score: 89, date: relativeDate(2, 0, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Audigy"] },
  { id: 7, scorecard: "SelectQuote Term Life v1", score: 86, date: relativeDate(2, 2, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"] },
  { id: 6, scorecard: "CS3 Nexstar v1", score: 93, date: relativeDate(2, 4, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"] },
  { id: 5, scorecard: "CS3 Services v2", score: 84, date: relativeDate(2, 6, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Services v2"] },
  { id: 4, scorecard: "AW IB Sales", score: 98, date: relativeDate(2, 8, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["AW IB Sales"] },
  { id: 3, scorecard: "CS3 Audigy", score: 90, date: relativeDate(2, 10, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Audigy"] },
  { id: 2, scorecard: "SelectQuote Term Life v1", score: 87, date: relativeDate(2, 12, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["SelectQuote Term Life v1"] },
  { id: 1, scorecard: "CS3 Nexstar v1", score: 94, date: relativeDate(2, 14, 0), status: "scored", hasFeedback: true, scoreCount: scorecardScoreCounts["CS3 Nexstar v1"] },
];

// Modify other items to include scoreResults
initialFeedbackItems.forEach(item => {
  if (!item.scoreResults) {
    item.scoreResults = sampleScoreResults;
  }
});

// Sort items by date, newest first
initialFeedbackItems.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

const FEEDBACK_TIME_RANGE_OPTIONS: TimeRangeOption[] = [
  { value: "recent", label: "Recent" },
  { value: "review", label: "With Feedback" },
  { value: "custom", label: "Custom" },
]

export default function FeedbackDashboard() {
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
  const [showNewAnnotationForm, setShowNewAnnotationForm] = useState<string | null>(null);
  const [thumbedUpScores, setThumbedUpScores] = useState<Set<string>>(new Set());
  const [feedbackItems, setFeedbackItems] = useState<any[]>([]);

  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }

    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)

    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

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
      case 'new':
      case 'scoring...':
        return 'bg-neutral text-primary-foreground h-6';
      case 'scored':
        return 'bg-true text-primary-foreground h-6';
      case 'error':
        return 'bg-destructive text-destructive-foreground dark:text-primary-foreground h-6';
      default:
        return 'bg-muted text-muted-foreground h-6';
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
    setShowNewAnnotationForm(null);
    setNewAnnotation({ value: "", explanation: "", annotation: "" });
  };

  const handleNewAnnotationSubmit = (scoreName: string) => {
    const newFeedbackItem = {
      ...newAnnotation,
      scoreName,
      timestamp: new Date().toISOString(),
      user: {
        name: "Current User", // Replace with actual user name
        initials: "CU" // Replace with actual user initials
      }
    };

    setFeedbackItems(prev => [...prev, newFeedbackItem]);

    // Find the selected item
    const selectedItemData = feedbackItems.find(item => item.id === selectedItem);

    if (selectedItemData) {
      // Update the score to show it's annotated
      const updatedScoreResults = selectedItemData.scoreResults.map(section => ({
        ...section,
        scores: section.scores.map(score => 
          score.name === scoreName 
            ? { ...score, isAnnotated: true, annotations: [...(score.annotations || []), newFeedbackItem] }
            : score
        )
      }));

      // Update the feedbackItems with the new score results
      setFeedbackItems(prev => prev.map(item => 
        item.id === selectedItem 
          ? { ...item, scoreResults: updatedScoreResults }
          : item
      ));
    }

    setShowNewAnnotationForm(null);
    setNewAnnotation({ value: "", explanation: "", annotation: "" });
  };

  const toggleNewAnnotationForm = (scoreName: string) => {
    if (showNewAnnotationForm === scoreName) {
      setShowNewAnnotationForm(null);
    } else {
      setShowNewAnnotationForm(scoreName);
      initializeNewAnnotation(feedbackItems.flatMap(item => item.scoreResults?.flatMap(section => section.scores)).find(score => score.name === scoreName));
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

    // Close the annotation form if it's open
    if (showNewAnnotationForm === scoreName) {
      setShowNewAnnotationForm(null);
    }

    // Reset the new annotation state
    setNewAnnotation({ value: "", explanation: "", annotation: "" });
  };

  const handleThumbsDown = (scoreName: string) => {
    setThumbedUpScores(prev => {
      const newSet = new Set(prev);
      newSet.delete(scoreName);
      return newSet;
    });
    toggleNewAnnotationForm(scoreName);
  };

  function renderScoreResult(score: any, isAnnotation = false) {
    return (
      <div className={`py-2 ${isAnnotation ? 'pl-4 border-l-2 ' + (score.isSystem ? 'border-secondary' : 'border-primary') : ''}`}>
        {isAnnotation ? (
          <>
            <div className="flex justify-end mb-2">
              <Badge className={getValueBadgeClass(score.value)}>{score.value}</Badge>
            </div>
            <div className="relative">
              <div 
                ref={(el) => textRef.current[score.name] = el}
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
                {(score.isAnnotated || feedbackItems[score.name]?.length > 0) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleAnnotations(score.name)}
                    className={`text-xs bg-secondary text-secondary-foreground hover:bg-secondary hover:text-secondary-foreground`}
                  >
                    <MessageCircleMore className="h-4 w-4" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleThumbsUp(score.name)}
                  className={`text-xs ${thumbedUpScores.has(score.name) ? 'bg-true text-primary-foreground hover:bg-true hover:text-primary-foreground' : 'hover:bg-muted hover:text-muted-foreground'}`}
                >
                  <ThumbsUp className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleThumbsDown(score.name)}
                  className="text-xs hover:bg-muted hover:text-muted-foreground"
                >
                  <ThumbsDown className="h-4 w-4" />
                </Button>
                <Badge className={getValueBadgeClass(score.value)}>{score.value}</Badge>
              </div>
            </div>
            <div className="relative">
              <div 
                ref={(el) => textRef.current[score.name] = el}
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
        {!isAnnotation && (score.isAnnotated || feedbackItems[score.name]?.length > 0) && expandedAnnotations.includes(score.name) && (
          <div className="mt-2 space-y-2">
            <div className="flex justify-between items-center mb-2">
              <h6 className="text-sm font-medium">Feedback</h6>
              <Button
                variant="outline"
                size="sm"
                onClick={() => toggleNewAnnotationForm(score.name)}
                className="text-xs"
              >
                <Plus className="h-4 w-4 mr-1" />
                Create
              </Button>
            </div>
            {[...(score.annotations || []), ...(feedbackItems[score.name] || [])].map((annotation, annotationIndex) => (
              <div key={annotationIndex} className="relative">
                {renderScoreResult(annotation, true)}
              </div>
            ))}
          </div>
        )}
        {!isAnnotation && showNewAnnotationForm === score.name && (
          <div className="mt-2 space-y-2 border-l-2 border-muted-foreground pl-4">
            <div className="mb-4">
              <h6 className="text-sm font-medium mb-2">Feedback</h6>
              <div className="space-y-2">
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
                <Input 
                  placeholder="Feedback" 
                  value={newAnnotation.annotation}
                  onChange={(e) => setNewAnnotation({...newAnnotation, annotation: e.target.value})}
                />
                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => cancelAnnotation(score.name)}>Cancel</Button>
                  <Button onClick={() => handleNewAnnotationSubmit(score.name)}>Submit Feedback</Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  function renderSelectedItem() {
    const selectedItemData = feedbackItems.find(item => item.id === selectedItem);

    return (
      <Card className="rounded-none sm:rounded-lg h-full flex flex-col">
        <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between py-4 px-4 sm:px-6 space-y-0">
          <div>
            <h2 className="text-xl font-semibold">{selectedItemData?.scorecard}</h2>
            <p className="text-sm text-muted-foreground">
              {getRelativeTime(selectedItemData?.date)}
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
          {selectedItemData && (
            <div className="space-y-4">
              {/* Metadata Section */}
              <div className="-mx-4 sm:-mx-6">
                <div
                  className="relative group bg-muted hover:bg-accent hover:text-accent-foreground cursor-pointer"
                  onClick={() => setIsMetadataExpanded(!isMetadataExpanded)}
                >
                  <div className="flex justify-between items-center px-4 sm:px-6 py-2">
                    <span className="text-md font-semibold">
                      Metadata
                    </span>
                    {isMetadataExpanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </div>
                </div>
              </div>
              {isMetadataExpanded && (
                <div className="mt-2">
                  <Table>
                    <TableBody>
                      {selectedItemData.metadata?.map((meta, index) => (
                        <TableRow key={index}>
                          <TableCell className="font-medium pl-0">{meta.key}</TableCell>
                          <TableCell className="text-right pr-0">{meta.value}</TableCell>
                        </TableRow>
                      )) || <TableRow><TableCell>No metadata available</TableCell></TableRow>}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Data Section */}
              <div className="-mx-4 sm:-mx-6">
                <div
                  className="relative group bg-muted hover:bg-accent hover:text-accent-foreground cursor-pointer"
                  onClick={() => setIsDataExpanded(!isDataExpanded)}
                >
                  <div className="flex justify-between items-center px-4 sm:px-6 py-2">
                    <span className="text-md font-semibold">
                      Data
                    </span>
                    {isDataExpanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </div>
                </div>
              </div>
              {isDataExpanded && (
                <div className="mt-2">
                  {selectedItemData.data?.map((line, index) => (
                    <p key={index} className="text-sm">
                      <span className="font-semibold">{line.speaker}: </span>
                      {line.text}
                    </p>
                  )) || <p>No data available</p>}
                </div>
              )}

              {/* Score Results Section */}
              <div className="-mx-4 sm:-mx-6 mb-4">
                <div className="px-4 sm:px-6 py-2 bg-muted">
                  <h4 className="text-md font-semibold">Score Results</h4>
                </div>
              </div>
              <div>
                {selectedItemData.scoreResults?.map((section, sectionIndex) => (
                  <div key={sectionIndex} className="mb-6">
                    <div className="-mx-4 sm:-mx-6 mb-4">
                      <div className="px-4 sm:px-6 py-2">
                        <h4 className="text-md font-semibold">{section.section}</h4>
                      </div>
                      <hr className="border-t border-border" />
                    </div>
                    <div>
                      {section.scores.map((score, scoreIndex) => (
                        <React.Fragment key={scoreIndex}>
                          {renderScoreResult(score)}
                          {scoreIndex < section.scores.length - 1 && (
                            <hr className="my-2 border-t border-border" />
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                )) || <p>No score results available</p>}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    )
  }

  const getFeedbackBadgeClass = (hasFeedback: boolean) => {
    return hasFeedback
      ? 'bg-true text-primary-foreground w-16 justify-center'
      : 'bg-false text-primary-foreground w-16 justify-center';
  };

  // Update the initialization of feedbackItems
  useEffect(() => {
    setFeedbackItems(initialFeedbackItems);
  }, []);

  return (
    <div className="space-y-4 h-full flex flex-col">
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
              {/* Add more SelectItem components as needed */}
            </SelectContent>
          </Select>
        </div>
        <div className="flex space-x-2">
          <FilterControl onFilterChange={handleFilterChange} availableFields={availableFields} />
          <TimeRangeSelector onTimeRangeChange={handleTimeRangeChange} options={FEEDBACK_TIME_RANGE_OPTIONS} />
        </div>
      </div>

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
                    <TableHead className="w-[50%]">Item</TableHead>
                    <TableHead className="w-[20%] text-right">Scores</TableHead>
                    <TableHead className="w-[30%] text-right">Feedback</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredItems.map((item) => (
                    <TableRow 
                      key={item.id} 
                      onClick={() => handleItemClick(item.id)} 
                      className="cursor-pointer transition-colors duration-200 hover:bg-muted"
                    >
                      <TableCell className="font-medium sm:pr-4">
                        <div className="sm:hidden">
                          <div className="flex justify-between items-start mb-2">
                            <div className="font-semibold">{item.scorecard}</div>
                            <Badge 
                              className={getFeedbackBadgeClass(item.hasFeedback)}
                            >
                              {item.hasFeedback ? 'Yes' : 'No'}
                            </Badge>
                          </div>
                          <div className="text-sm text-muted-foreground">{getRelativeTime(item.date)}</div>
                          <div className="text-sm text-muted-foreground mt-1">Scores: {item.scoreCount}</div>
                        </div>
                        <div className="hidden sm:block">
                          {item.scorecard}
                          <div className="text-sm text-muted-foreground">{getRelativeTime(item.date)}</div>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">{item.scoreCount}</TableCell>
                      <TableCell className="text-right">
                        <Badge 
                          className={getFeedbackBadgeClass(item.hasFeedback)}
                        >
                          {item.hasFeedback ? 'Yes' : 'No'}
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
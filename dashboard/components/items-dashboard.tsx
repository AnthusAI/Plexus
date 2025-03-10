"use client"
import React from "react"
import { useState, useMemo, useEffect, useRef, useCallback } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, Loader2 } from "lucide-react"
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
import type { FeedbackItem } from '@/components/feedback-dashboard'
import ItemCard, { ItemData } from './items/ItemCard'
import { amplifyClient, graphqlRequest } from '@/utils/amplify-client'
import { useAuthenticator } from '@aws-amplify/ui-react'

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
  id: string;
  externalId?: string;
  description?: string;
  accountId: string;
  scorecardId?: string;
  scoreId?: string;
  evaluationId?: string;
  updatedAt?: string;
  createdAt?: string;
  isEvaluation: boolean;
  
  // Fields for UI compatibility with existing code
  scorecard?: string;
  score?: number;
  date?: string;
  status?: string;
  results?: number;
  inferences?: number;
  cost?: string;
}

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
  const [selectedItem, setSelectedItem] = useState<string | null>(null)
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
  const [items, setItems] = useState<Item[]>([]);
  const [sampleMethod, setSampleMethod] = useState("All");
  const [sampleCount, setSampleCount] = useState(100);
  const [scoreResults, setScoreResults] = useState(sampleScoreResults);
  const [leftPanelWidth, setLeftPanelWidth] = useState(50);
  const [isLoading, setIsLoading] = useState(false);
  const [nextToken, setNextToken] = useState<string | null>(null);
  const { user } = useAuthenticator();
  const [accountId, setAccountId] = useState<string | null>(null);
  
  // Constants
  const ACCOUNT_KEY = 'call-criteria';

  // Fetch items from the API
  useEffect(() => {
    const fetchItems = async () => {
      if (!user) return;
      
      setIsLoading(true);
      try {
        // Get the user's account ID by querying for the account with the key 'call-criteria'
        const accountResult = await amplifyClient.Account.list({
          filter: { key: { eq: ACCOUNT_KEY } }
        });
        
        console.log(`Found ${accountResult.data.length} accounts with key ${ACCOUNT_KEY}`);
        
        if (accountResult.data.length === 0) {
          console.warn('No account found with key:', ACCOUNT_KEY);
          
          // For development purposes, you might want to create a test account
          // Uncomment the following code to create a test account
          /*
          try {
            console.log('Creating a test account...');
            const createAccountResponse = await amplifyClient.Account.create({
              name: 'Test Account',
              key: ACCOUNT_KEY,
              description: 'Test account created automatically'
            });
            
            if (createAccountResponse.data) {
              console.log('Test account created:', createAccountResponse.data);
              setAccountId(createAccountResponse.data.id);
              // Continue with empty items for now
              setItems([]);
            }
          } catch (createError) {
            console.error('Error creating test account:', createError);
          }
          */
          
          setIsLoading(false);
          return;
        }
        
        const foundAccountId = accountResult.data[0].id;
        setAccountId(foundAccountId);
        
        // Use the GSI for accountId with updatedAt as sort key
        const response = await amplifyClient.Item.list({
          filter: { accountId: { eq: foundAccountId } },
          sort: { field: 'updatedAt', direction: 'desc' },
          limit: 20
        });
        
        console.log(`Found ${response.data.length} items for account ID ${foundAccountId}`);
        console.log('API response:', JSON.stringify(response, null, 2));
        
        // Try a direct GraphQL query as well
        let itemsFromDirectQuery: any[] = [];
        let nextTokenFromDirectQuery: string | null = null;
        
        try {
          const directQuery = await graphqlRequest<{ listItems: { items: any[], nextToken: string | null } }>(`
            query ListItemsDirect {
              listItems(filter: {accountId: {eq: "${foundAccountId}"}}, limit: 20) {
                items {
                  id
                  externalId
                  description
                  accountId
                  scorecardId
                  scoreId
                  evaluationId
                  updatedAt
                  createdAt
                  isEvaluation
                }
                nextToken
              }
            }
          `);
          console.log('Direct GraphQL query response:', JSON.stringify(directQuery, null, 2));
          
          if (directQuery.data?.listItems?.items) {
            itemsFromDirectQuery = directQuery.data.listItems.items;
            nextTokenFromDirectQuery = directQuery.data.listItems.nextToken;
          }
        } catch (graphqlError) {
          console.error('Error with direct GraphQL query:', graphqlError);
        }
        
        // Use the items from the direct query if available, otherwise use the response from amplifyClient
        const itemsToUse = itemsFromDirectQuery.length > 0 ? itemsFromDirectQuery : response.data;
        const nextTokenToUse = itemsFromDirectQuery.length > 0 ? nextTokenFromDirectQuery : response.nextToken;
        
        // If no items are found, we'll log this information
        if (itemsToUse.length === 0) {
          console.log('No items found for this account. You may need to create some items first.');
        }
        
        // Get unique scorecard IDs to fetch their names
        const scorecardIds = [...new Set(
          itemsToUse
            .filter(item => item.scorecardId)
            .map(item => item.scorecardId)
        )];
        
        // Fetch scorecard names if there are any scorecard IDs
        const scorecardMap: Record<string, string> = {};
        if (scorecardIds.length > 0) {
          try {
            // Fetch scorecards in parallel
            const scorecardPromises = scorecardIds.map(async (id) => {
              if (!id) return null;
              const result = await amplifyClient.Scorecard.get({ id });
              return result.data;
            });
            
            const scorecards = await Promise.all(scorecardPromises);
            
            // Create a map of scorecard ID to name
            scorecards.forEach(scorecard => {
              if (scorecard && scorecard.id) {
                scorecardMap[scorecard.id] = scorecard.name || 'Unnamed Scorecard';
              }
            });
          } catch (error) {
            console.error("Error fetching scorecards:", error);
          }
        }
        
        // Transform the data to match the expected format
        const transformedItems = itemsToUse.map(item => {
          // Get the scorecard name if scorecardId is available
          let scorecardName = "Unknown Scorecard";
          if (item.scorecardId && scorecardMap[item.scorecardId]) {
            scorecardName = scorecardMap[item.scorecardId];
          } else if (item.scorecardId) {
            scorecardName = `Scorecard ${item.scorecardId.substring(0, 8)}`;
          }
          
          return {
            id: item.id,
            accountId: item.accountId,
            externalId: item.externalId,
            description: item.description,
            scorecardId: item.scorecardId,
            scoreId: item.scoreId,
            evaluationId: item.evaluationId,
            updatedAt: item.updatedAt,
            createdAt: item.createdAt,
            isEvaluation: item.isEvaluation,
            // UI compatibility fields
            scorecard: scorecardName,
            date: item.updatedAt || item.createdAt,
            status: "Done", // Default status
            results: 0,
            inferences: 0,
            cost: "$0.000",
            score: 0
          } as Item;
        });
        
        setItems(transformedItems);
        setNextToken(nextTokenToUse);
      } catch (error) {
        console.error("Error fetching items:", error);
        // Don't keep the mock data if there's an error
        setItems([]);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchItems();
  }, [user]);

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
    // For debugging
    console.log("Filtering items:", {
      itemsCount: items.length,
      selectedScorecard,
      filterConfigLength: filterConfig.length
    });
    
    return items.filter(item => {
      if (!selectedScorecard && filterConfig.length === 0) return true
      
      let scorecardMatch = !selectedScorecard || item.scorecard === selectedScorecard
      
      if (filterConfig.length === 0) return scorecardMatch

      return scorecardMatch && filterConfig.some(group => {
        return group.conditions.every(condition => {
          const itemValue = String(item[condition.field as keyof typeof item] || '')
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
      <div className="h-full flex flex-col">
        <ItemCard
          variant="detail"
          item={selectedItemData as ItemData}
          isFullWidth={isFullWidth}
          onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
          onClose={() => {
            setSelectedItem(null);
            setIsFullWidth(false);
          }}
          getBadgeVariant={getBadgeVariant}
        />
        
        <div className="flex-1 overflow-auto">
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
        </div>
      </div>
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

  const handleItemClick = (itemId: string) => {
    setSelectedItem(itemId)
    if (isNarrowViewport) {
      setIsFullWidth(true)
    }
  }

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    
    // Get the initial mouse position and panel width
    const startX = e.clientX;
    const startWidth = leftPanelWidth;
    
    // Get the container element for width calculations
    const container = e.currentTarget.parentElement;
    if (!container) return;
    
    // Create the drag handler
    const handleDrag = (e: MouseEvent) => {
      // Calculate how far the mouse has moved
      const deltaX = e.clientX - startX;
      
      // Calculate the container width for percentage calculation
      const containerWidth = container.getBoundingClientRect().width;
      
      // Calculate the new width as a percentage of the container
      const deltaPercentage = (deltaX / containerWidth) * 100;
      const newWidth = Math.min(Math.max(startWidth + deltaPercentage, 20), 80);
      
      // Update the state with the new width
      requestAnimationFrame(() => {
        setLeftPanelWidth(newWidth);
      });
    };
    
    // Create the cleanup function
    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag);
      document.removeEventListener('mouseup', handleDragEnd);
      document.body.style.cursor = '';
    };
    
    // Set the cursor for the entire document during dragging
    document.body.style.cursor = 'col-resize';
    
    // Add the event listeners
    document.addEventListener('mousemove', handleDrag);
    document.addEventListener('mouseup', handleDragEnd);
  };

  const handleLoadMore = async () => {
    if (!user || !nextToken || isLoading || !accountId) return;
    
    setIsLoading(true);
    try {
      // Use the stored account ID
      
      // Use the GSI for accountId with updatedAt as sort key
      const response = await amplifyClient.Item.list({
        filter: { accountId: { eq: accountId } },
        sort: { field: 'updatedAt', direction: 'desc' },
        limit: 20,
        nextToken
      });
      
      // Try a direct GraphQL query as well
      let itemsFromDirectQuery: any[] = [];
      let nextTokenFromDirectQuery: string | null = null;
      
      try {
        const directQuery = await graphqlRequest<{ listItems: { items: any[], nextToken: string | null } }>(`
          query ListItemsDirect {
            listItems(filter: {accountId: {eq: "${accountId}"}}, limit: 20, nextToken: "${nextToken}") {
              items {
                id
                externalId
                description
                accountId
                scorecardId
                scoreId
                evaluationId
                updatedAt
                createdAt
                isEvaluation
              }
              nextToken
            }
          }
        `);
        
        if (directQuery.data?.listItems?.items) {
          itemsFromDirectQuery = directQuery.data.listItems.items;
          nextTokenFromDirectQuery = directQuery.data.listItems.nextToken;
        }
      } catch (graphqlError) {
        console.error('Error with direct GraphQL query in load more:', graphqlError);
      }
      
      // Use the items from the direct query if available, otherwise use the response from amplifyClient
      const itemsToUse = itemsFromDirectQuery.length > 0 ? itemsFromDirectQuery : response.data;
      const nextTokenToUse = itemsFromDirectQuery.length > 0 ? nextTokenFromDirectQuery : response.nextToken;
      
      // Get unique scorecard IDs to fetch their names
      const scorecardIds = [...new Set(
        itemsToUse
          .filter(item => item.scorecardId)
          .map(item => item.scorecardId)
      )];
      
      // Fetch scorecard names if there are any scorecard IDs
      const scorecardMap: Record<string, string> = {};
      if (scorecardIds.length > 0) {
        try {
          // Fetch scorecards in parallel
          const scorecardPromises = scorecardIds.map(async (id) => {
            if (!id) return null;
            const result = await amplifyClient.Scorecard.get({ id });
            return result.data;
          });
          
          const scorecards = await Promise.all(scorecardPromises);
          
          // Create a map of scorecard ID to name
          scorecards.forEach(scorecard => {
            if (scorecard && scorecard.id) {
              scorecardMap[scorecard.id] = scorecard.name || 'Unnamed Scorecard';
            }
          });
        } catch (error) {
          console.error("Error fetching scorecards:", error);
        }
      }
      
      // Transform the data to match the expected format
      const transformedItems = itemsToUse.map(item => {
        // Get the scorecard name if scorecardId is available
        let scorecardName = "Unknown Scorecard";
        if (item.scorecardId && scorecardMap[item.scorecardId]) {
          scorecardName = scorecardMap[item.scorecardId];
        } else if (item.scorecardId) {
          scorecardName = `Scorecard ${item.scorecardId.substring(0, 8)}`;
        }
        
        return {
          id: item.id,
          accountId: item.accountId,
          externalId: item.externalId,
          description: item.description,
          scorecardId: item.scorecardId,
          scoreId: item.scoreId,
          evaluationId: item.evaluationId,
          updatedAt: item.updatedAt,
          createdAt: item.createdAt,
          isEvaluation: item.isEvaluation,
          // UI compatibility fields
          scorecard: scorecardName,
          date: item.updatedAt || item.createdAt,
          status: "Done", // Default status
          results: 0,
          inferences: 0,
          cost: "$0.000",
          score: 0
        } as Item;
      });
      
      // Append the new items to the existing items
      setItems(prevItems => [...prevItems, ...transformedItems]);
      setNextToken(nextTokenToUse);
    } catch (error) {
      console.error("Error fetching more items:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full p-1.5">
      <div className="flex flex-wrap justify-between items-start gap-4 mb-3">
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

      <div className="flex-grow flex flex-col overflow-hidden">
        {selectedItem && (isNarrowViewport || isFullWidth) ? (
          <div className="flex-grow overflow-hidden">
            {renderSelectedItem()}
          </div>
        ) : (
          <div className={`flex ${isNarrowViewport ? 'flex-col' : ''} h-full`}>
            <div 
              className={`${isFullWidth ? 'hidden' : 'flex-1'} overflow-auto`}
              style={selectedItem && !isNarrowViewport && !isFullWidth ? {
                width: `${leftPanelWidth}%`
              } : undefined}
            >
              <div>
                <div className="@container h-full">
                  {isLoading && items.length === 0 ? (
                    <div className="flex justify-center items-center h-40">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                      <span className="ml-2 text-lg">Loading items...</span>
                    </div>
                  ) : (
                    <>
                      {filteredItems.length === 0 ? (
                        <div className="flex flex-col justify-center items-center h-40 text-center">
                          <Info className="h-8 w-8 text-muted-foreground mb-2" />
                          <h3 className="text-lg font-medium">No items found</h3>
                          <p className="text-muted-foreground mt-1">
                            {filterConfig.length > 0 || selectedScorecard 
                              ? "Try adjusting your filters" 
                              : "Create your first item to get started"}
                          </p>
                        </div>
                      ) : (
                        <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3">
                          {filteredItems.map((item) => (
                            <ItemCard
                              key={item.id}
                              variant="grid"
                              item={item as ItemData}
                              isSelected={selectedItem === item.id}
                              onClick={() => handleItemClick(item.id)}
                              getBadgeVariant={getBadgeVariant}
                            />
                          ))}
                        </div>
                      )}
                      
                      {nextToken && filteredItems.length > 0 && (
                        <div className="flex justify-center mt-6">
                          <Button 
                            variant="outline" 
                            onClick={handleLoadMore}
                            disabled={isLoading}
                          >
                            {isLoading ? (
                              <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Loading...
                              </>
                            ) : (
                              'Load More'
                            )}
                          </Button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>

            {selectedItem && !isNarrowViewport && !isFullWidth && (
              <div
                className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
                onMouseDown={handleDragStart}
              >
                <div className="absolute inset-0 rounded-full transition-colors duration-150 
                  group-hover:bg-accent" />
              </div>
            )}

            {selectedItem && !isNarrowViewport && !isFullWidth && (
              <div 
                className="overflow-hidden"
                style={{ width: `${100 - leftPanelWidth}%` }}
              >
                {renderSelectedItem()}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

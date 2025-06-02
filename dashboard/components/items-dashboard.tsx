"use client"
import React, { useContext, useEffect, useMemo, useRef, useState, useCallback, Suspense } from "react"
import { useRouter, useSearchParams, useParams } from 'next/navigation'
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, Loader2, Search } from "lucide-react"
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
import remarkBreaks from 'remark-breaks'
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import Link from 'next/link'
import { FilterControl, FilterConfig } from "@/components/filter-control"
import ScorecardContext from "@/components/ScorecardContext"
import ItemContext from "@/components/ItemContext"
import { formatTimeAgo } from '@/utils/format-time'
import type { FeedbackItem } from '@/types/feedback'
import ItemCard, { ItemData } from './items/ItemCard'
import { amplifyClient, graphqlRequest } from '@/utils/amplify-client'
import { useAuthenticator } from '@aws-amplify/ui-react'
import { ScorecardContextProps } from "./ScorecardContext"
import { observeItemCreations, observeItemUpdates, observeScoreResultChanges } from '@/utils/subscriptions'
import { toast } from 'sonner'
import { useAccount } from '@/app/contexts/AccountContext'
import { ItemsDashboardSkeleton, ItemCardSkeleton } from './loading-skeleton'
import { ScoreResultCountManager, type ScoreResultCount } from '@/utils/score-result-counter'

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
  timestamp: string; // ISO string for when the item was created/updated
  duration?: number; // Duration in seconds (optional for elapsed time display)
  scorecards: Array<{
    scorecardId: string;
    scorecardName: string;
    resultCount: number;
  }>; // List of scorecards with result counts
  
  // Core fields
  externalId?: string;
  description?: string;
  accountId: string;
  evaluationId?: string;
  updatedAt?: string;
  createdAt?: string;
  isEvaluation: boolean;
  identifiers?: string | Array<{
    name: string;
    value: string;
    url?: string;
    position?: number;
  }>; // Support both JSON string (legacy) and new array format
  isNew?: boolean;
  isLoadingResults?: boolean;
  
  // Legacy fields for backwards compatibility (will be phased out)
  date?: string;
  status?: string;
  results?: number;
  inferences?: number;
  cost?: string;
  groupedScoreResults?: GroupedScoreResults;
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

// Memoized grid item component to prevent unnecessary re-renders
const MemoizedGridItemCard = React.memo(({ 
  item, 
  scoreCount, 
  selectedItem, 
  handleItemClick, 
  getBadgeVariant, 
  scoreCountManagerRef,
  itemRefsMap
}: {
  item: Item;
  scoreCount: ScoreResultCount | undefined;
  selectedItem: string | null;
  handleItemClick: (itemId: string) => void;
  getBadgeVariant: (status: string) => string;
  scoreCountManagerRef: React.MutableRefObject<ScoreResultCountManager | null>;
  itemRefsMap: React.MutableRefObject<Map<string, HTMLDivElement | null>>;
}) => {
  const itemWithCount = useMemo(() => ({
    ...item,
    results: scoreCount?.count || item.results,
    isLoadingResults: scoreCount?.isLoading || false,
    scorecardBreakdown: scoreCount?.scorecardBreakdown || undefined,
    // Map scorecardBreakdown to the new scorecards field
    scorecards: scoreCount?.scorecardBreakdown ? 
      scoreCount.scorecardBreakdown.map(breakdown => ({
        scorecardId: breakdown.scorecardId,
        scorecardName: breakdown.scorecardName,
        resultCount: breakdown.count
      })) : 
      item.scorecards || []
  } as ItemData & { isLoadingResults: boolean }), [
    item,
    scoreCount?.count,
    scoreCount?.isLoading,
    scoreCount?.scorecardBreakdown
  ]);
  
  const handleClick = useCallback(() => handleItemClick(item.id), [handleItemClick, item.id]);
  
  // Combined ref callback to handle both score count observation and item ref tracking
  const combinedRef = useCallback((el: HTMLDivElement | null) => {
    // Store ref for scroll-to-view functionality
    itemRefsMap.current.set(item.id, el);
    
    // Handle score count observation
    if (el && scoreCountManagerRef.current) {
      scoreCountManagerRef.current.observeItem(el, item.id);
    }
  }, [item.id, scoreCountManagerRef, itemRefsMap]);
  
  return (
    <ItemCard
      key={item.id}
      variant="grid"
      item={itemWithCount}
      isSelected={selectedItem === item.id}
      onClick={handleClick}
      getBadgeVariant={getBadgeVariant}
      ref={combinedRef}
    />
  );
});

MemoizedGridItemCard.displayName = 'MemoizedGridItemCard';

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
      remarkPlugins={[remarkBreaks]}
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

// First, add a ScoreResult interface
interface ScoreResult {
  id: string;
  value: string;
  explanation?: string;
  confidence?: number | null;
  itemId: string;
  accountId: string;
  scorecardId: string;
  scoreId: string;
  scorecard?: {
    id: string;
    name: string;
  };
  score?: {
    id: string;
    name: string;
  };
  updatedAt?: string;
  createdAt?: string;
}

// Add a GroupedScoreResults interface for organizing results by scorecard
interface GroupedScoreResults {
  [scorecardId: string]: {
    scorecardName: string;
    scores: {
      scoreId: string;
      scoreName: string;
    }[];
  }
}

// Helper function to transform identifiers from GraphQL response
const transformIdentifiers = (item: any) => {
  // First try to get from new itemIdentifiers relationship
  if (item.itemIdentifiers?.items?.length > 0) {
    const transformedIdentifiers = item.itemIdentifiers.items
      .map((identifier: any) => ({
        name: identifier.name,
        value: identifier.value,
        url: identifier.url,
        position: identifier.position
      }))
      .sort((a: any, b: any) => (a.position || 0) - (b.position || 0));
    
    console.log('🔍 IDENTIFIER TRANSFORM DEBUG:', {
      itemId: item.id,
      originalData: item.itemIdentifiers?.items,
      transformedData: transformedIdentifiers,
      fallbackData: item.identifiers
    });
    
    return transformedIdentifiers;
  }
  
  // Fall back to legacy identifiers field
  console.log('🔍 IDENTIFIER FALLBACK DEBUG:', {
    itemId: item.id,
    hasItemIdentifiers: !!item.itemIdentifiers,
    itemIdentifiersCount: item.itemIdentifiers?.items?.length || 0,
    fallbackData: item.identifiers
  });
  
  return item.identifiers;
};

// Helper function to transform item from GraphQL response to Item interface
const transformItem = (item: any, options: { isNew?: boolean } = {}): Item => {
  return {
    // New required fields
    id: item.id,
    timestamp: item.createdAt || item.updatedAt || new Date().toISOString(),
    scorecards: [], // Will be populated with actual data later
    
    // Core fields
    accountId: item.accountId,
    externalId: item.externalId,
    description: item.description,
    evaluationId: item.evaluationId,
    updatedAt: item.updatedAt,
    createdAt: item.createdAt,
    isEvaluation: item.isEvaluation,
    identifiers: transformIdentifiers(item),
    isNew: options.isNew || false,
    isLoadingResults: false,
    
    // Legacy fields for backwards compatibility
    date: item.createdAt || item.updatedAt,
    status: "Done",
    results: 0,
    inferences: 0,
    cost: "$0.000",
    groupedScoreResults: {}
  };
};

function ItemsDashboardInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const params = useParams()
  const [selectedItem, setSelectedItem] = useState<string | null>(null)
  
  // Debug wrapper for setSelectedItem to track changes
  const debugSetSelectedItem = React.useCallback((itemId: string | null) => {
    console.log('🎯 SELECTED ITEM CHANGE:', {
      from: selectedItem,
      to: itemId,
      stack: new Error().stack?.split('\n').slice(1, 4).join('\n')
    });
    setSelectedItem(itemId);
  }, []); // Empty deps to avoid circular updates
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
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [nextToken, setNextToken] = useState<string | null>(null);
  const { user } = useAuthenticator();
  // Use the account context instead of local state
  const { selectedAccount, isLoadingAccounts } = useAccount();
  const itemSubscriptionRef = useRef<{ unsubscribe: () => void } | null>(null);
  const itemUpdateSubscriptionRef = useRef<{ unsubscribe: () => void } | null>(null);
  const scoreResultSubscriptionRef = useRef<{ unsubscribe: () => void } | null>(null);
  const scoreCountManagerRef = useRef<ScoreResultCountManager | null>(null);
  const [scoreResultCounts, setScoreResultCounts] = useState<Map<string, ScoreResultCount>>(new Map());
  const [specificItemLoading, setSpecificItemLoading] = useState(false);
  const [failedItemFetches, setFailedItemFetches] = useState<Set<string>>(new Set());
  const refetchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // Ref map to track item elements for scroll-to-view functionality
  const itemRefsMap = useRef<Map<string, HTMLDivElement | null>>(new Map());

  // Search state
  const [searchValue, setSearchValue] = useState<string>('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const searchErrorTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // Enhanced scroll-to-item function for deep-linking with retry logic
  const scrollToSelectedItem = useCallback((itemId: string, maxRetries = 10, retryDelay = 100) => {
    let attempts = 0;
    
    const attemptScroll = () => {
      attempts++;
      const itemElement = itemRefsMap.current.get(itemId);
      
      if (itemElement) {
        console.log(`📍 Scrolling to item ${itemId} (attempt ${attempts})`);
        itemElement.scrollIntoView({
          behavior: 'smooth',
          block: 'start', // Align to the top of the container
          inline: 'nearest'
        });
        return true; // Success
      } else if (attempts < maxRetries) {
        console.log(`⏱️ Retry ${attempts}/${maxRetries} for item ${itemId}. Available refs:`, Array.from(itemRefsMap.current.keys()).slice(0, 5));
        setTimeout(attemptScroll, retryDelay);
        return false; // Retry needed
      } else {
        console.log(`❌ Failed to scroll to item ${itemId} after ${maxRetries} attempts. Available refs:`, Array.from(itemRefsMap.current.keys()));
        return false; // Failed
      }
    };
    
    // Start with immediate attempt, then use requestAnimationFrame for subsequent attempts
    requestAnimationFrame(attemptScroll);
  }, []);

  // Search for item by identifier
  const handleSearch = useCallback(async (identifier: string) => {
    if (!identifier.trim()) return;
    
    setIsSearching(true);
    setSearchError(null);
    
    try {
      const response = await graphqlRequest<{
        listIdentifierByValue: {
          items: Array<{
            id: string;
            itemId?: string;
          }>;
        };
      }>(`
        query ListIdentifierByValue($value: String!) {
          listIdentifierByValue(value: $value) {
            items {
              id
              itemId
            }
          }
        }
      `, {
        value: identifier.trim()
      });
      
      const identifiers = response.data?.listIdentifierByValue?.items;
      
      if (identifiers && identifiers.length > 0) {
        // Use the first item found
        const identifier = identifiers[0];
        const itemId = identifier.itemId || identifier.id; // Try itemId first, fallback to id
        if (itemId) {
          // Navigate to the item
          router.push(`/lab/items/${itemId}`);
          setSearchValue(''); // Clear search on success
        } else {
          setSearchError('Item not found for this identifier');
        }
      } else {
        setSearchError('No item found with this identifier');
        // Set timeout to clear error after 5 seconds
        if (searchErrorTimeoutRef.current) {
          clearTimeout(searchErrorTimeoutRef.current);
        }
        searchErrorTimeoutRef.current = setTimeout(() => {
          setSearchError(null);
        }, 5000);
      }
    } catch (error) {
      console.error('Search error:', error);
      setSearchError('Error searching for item');
      // Set timeout to clear error after 5 seconds
      if (searchErrorTimeoutRef.current) {
        clearTimeout(searchErrorTimeoutRef.current);
      }
      searchErrorTimeoutRef.current = setTimeout(() => {
        setSearchError(null);
      }, 5000);
    } finally {
      setIsSearching(false);
    }
  }, [router]);

  // Handle search form submission
  const handleSearchSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(searchValue);
  }, [handleSearch, searchValue]);
  
  // Function to fetch a specific item by ID
  const fetchSpecificItem = useCallback(async (itemId: string) => {
    console.log('🔍 fetchSpecificItem called:', { 
      itemId, 
      hasSelectedAccount: !!selectedAccount,
      timestamp: new Date().toISOString(),
      alreadyFailed: failedItemFetches.has(itemId)
    });
    
    if (!selectedAccount) {
      console.log('❌ No selected account, returning null');
      return null;
    }
    
    // Check if we've already failed to fetch this item, but allow retries on account change
    if (failedItemFetches.has(itemId)) {
      console.log('⏭️ Previously failed to fetch this item, but will retry');
    }
    
    console.log('⏳ Setting specificItemLoading to true');
    setSpecificItemLoading(true);
    
    // Add a timeout to prevent hanging forever
    const timeoutId = setTimeout(() => {
      console.log('⏰ fetchSpecificItem timeout for item:', itemId);
      setSpecificItemLoading(false);
      setFailedItemFetches(prev => new Set(prev).add(itemId));
    }, 30000); // 30 second timeout
    
    try {
      console.log('🚀 Making GraphQL request for item:', itemId);
      const response = await graphqlRequest<{
        getItem: {
          id: string;
          externalId?: string;
          description?: string;
          accountId: string;
          evaluationId?: string;
          updatedAt?: string;
          createdAt?: string;
          isEvaluation: boolean;
        }
      }>(`
        query GetItem($id: ID!) {
          getItem(id: $id) {
            id
            externalId
            description
            accountId
            evaluationId
            updatedAt
            createdAt
            isEvaluation
            identifiers
            itemIdentifiers {
              items {
                id
                name
                value
                url
                position
              }
            }
          }
        }
      `, {
        id: itemId
      });
      
      console.log('📡 GraphQL response received:', response);
      
      if (response.data?.getItem) {
        const item = response.data.getItem;
        console.log('✅ Item found, transforming:', item);
        
        // Transform the item to match our expected format
        const transformedItem = transformItem(item, { isNew: false });
        console.log('🔄 Transformed item:', transformedItem);
        
        // Add the item to the beginning of the list if it's not already there
        setItems(prevItems => {
          const exists = prevItems.some(existingItem => existingItem.id === item.id);
          if (!exists) {
            console.log('➕ Adding fetched item to list');
            return [transformedItem, ...prevItems];
          }
          console.log('⚠️ Item already exists in list');
          return prevItems;
        });
        
        return transformedItem;
      }
      
      console.log('❌ Item not found in response, marking as failed');
      // Item not found, mark as failed
      setFailedItemFetches(prev => new Set(prev).add(itemId));
      return null;
    } catch (error) {
      console.error('💥 Error fetching specific item:', error);
      // Mark as failed on error too
      setFailedItemFetches(prev => new Set(prev).add(itemId));
      return null;
    } finally {
      clearTimeout(timeoutId);
      console.log('🏁 Setting specificItemLoading to false');
      setSpecificItemLoading(false);
    }
  }, [selectedAccount]); // Removed state dependencies to avoid circular updates
  
  // Clear failed fetches when account changes
  useEffect(() => {
    if (selectedAccount) {
      console.log('🧹 Clearing failed fetches due to account change');
      setFailedItemFetches(new Set());
    }
  }, [selectedAccount?.id]);
  
  // Track the previous item ID to only scroll when it actually changes
  const prevItemIdRef = useRef<string | null>(null);
  

  
  // Sync URL parameter with selected item and implement deep-linking behavior
  useEffect(() => {
    const itemId = params.id as string
    
    console.log('🔄 Deep-link sync useEffect triggered:', { 
      itemId, 
      selectedItem, 
      isLoading, 
      hasSelectedAccount: !!selectedAccount,
      isLoadingAccounts,
      isNarrowViewport,
      itemsCount: items.length,
      paramsObject: params,
      failedItemFetches: Array.from(failedItemFetches)
    });
    
    if (itemId) {
      // Always set the selected item if it's different
      if (itemId !== selectedItem) {
        console.log('📝 Setting selected item:', itemId);
        debugSetSelectedItem(itemId)
      }
      
      // Don't proceed with view logic if accounts are still loading
      if (isLoadingAccounts) {
        console.log('⏳ Accounts still loading, waiting...');
        return;
      }
      
      // Check if the deep-linked item is in the first page of results (inline check to avoid dependency)
      const itemInFirstPage = items.some(item => item.id === itemId);
      console.log('🔍 Deep-link analysis:', { 
        itemId, 
        itemInFirstPage, 
        itemsLength: items.length,
        isNarrowViewport 
      });
      
      if (itemInFirstPage) {
        console.log('✅ Item is in first page - showing grid and scrolling to item');
        // Item is in the first page: show the grid and scroll to the item
        if (!isNarrowViewport) {
          setIsFullWidth(false); // Ensure grid is visible
        }
        
        // Scroll to the item if this is a new selection
        if (prevItemIdRef.current !== itemId) {
          console.log('🎯 Deep-link scrolling to item in grid');
          // Use the enhanced scroll function with retry logic
          scrollToSelectedItem(itemId);
          prevItemIdRef.current = itemId;
        }
      } else if (selectedAccount) {
        console.log('🚀 Item not in first page - fetching and showing full-width');
        // Item is not in the first page: fetch it and show in full-width mode (hide grid)
        if (!isNarrowViewport) {
          setIsFullWidth(true); // Hide grid, show full-width
        }
        
        // Fetch the specific item since it's not in the current page
        fetchSpecificItem(itemId);
        prevItemIdRef.current = itemId;
      } else {
        console.log('⏭️ Not proceeding because no selected account');
      }
    } else if (!itemId && selectedItem && !isLoadingAccounts) {
      // Clear selection and reset to grid view when no item is selected
      console.log('🧹 Clearing deep-link - returning to grid view');
      debugSetSelectedItem(null)
      setIsFullWidth(false) // Always show grid when no item is selected
      prevItemIdRef.current = null;
    }
  }, [params.id, selectedAccount, isLoadingAccounts, isNarrowViewport]) // Removed items.length and isItemInFirstPage to prevent re-running on real-time updates

  // Additional useEffect to ensure scrolling works when items are loaded and there's a selected item in the grid
  useEffect(() => {
    if (selectedItem && items.length > 0 && !isLoading && !isLoadingAccounts) {
      const itemInFirstPage = items.some(item => item.id === selectedItem);
      
      console.log('🔄 Items loaded, checking for scroll opportunity:', {
        selectedItem,
        itemInFirstPage,
        itemsCount: items.length,
        isFullWidth,
        isNarrowViewport
      });
      
      // Only scroll if the item is in the first page and we're showing the grid
      if (itemInFirstPage && !isFullWidth && !isNarrowViewport) {
        console.log('🎯 Triggering scroll for loaded item in grid');
        // Use a small delay to ensure the grid is fully rendered
        setTimeout(() => {
          scrollToSelectedItem(selectedItem);
        }, 50);
      }
    }
  }, [selectedItem, items.length, isLoading, isLoadingAccounts, isFullWidth, isNarrowViewport, scrollToSelectedItem]);

  
  // Add a ref for the intersection observer
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  
  // Define handleLoadMore with useCallback to ensure it's stable across renders
  const handleLoadMore = useCallback(async () => {
    if (isLoadingMore || !nextToken) return;
    
    setIsLoadingMore(true);
    
    try {
      // Use the selectedAccount from context
      if (!selectedAccount) {
        console.error('No account selected in context');
        setIsLoadingMore(false);
        return;
      }
      
      let itemsFromDirectQuery: any[] = [];
      let nextTokenFromDirectQuery: string | null = null;
      
      try {
        // Determine if we should filter by scorecard, score, or account
        const useScorecard = selectedScorecard !== null && selectedScorecard !== undefined;
        const useScore = selectedScore !== null && selectedScore !== undefined;
        
        
        if (useScore) {
          // If a score is selected, filter by scoreId
          const directQuery = await graphqlRequest<{ listItemByScoreIdAndCreatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsMoreDirect($scoreId: String!, $limit: Int!, $nextToken: String) {
              listItemByScoreIdAndCreatedAt(
                scoreId: $scoreId, 
                sortDirection: DESC,
                limit: $limit,
                nextToken: $nextToken
              ) {
                items {
                  id
                  externalId
                  description
                  accountId
                  evaluationId
                  updatedAt
                  createdAt
                  isEvaluation
                  identifiers
                  itemIdentifiers {
                    items {
                      id
                      name
                      value
                      url
                      position
                    }
                  }
                }
                nextToken
              }
            }
          `, {
            scoreId: selectedScore,
            limit: 100,
            nextToken: nextToken
          });
          
          if (directQuery.data?.listItemByScoreIdAndCreatedAt?.items) {
            // No need to sort as the GSI already returns items sorted by createdAt
            itemsFromDirectQuery = directQuery.data.listItemByScoreIdAndCreatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByScoreIdAndCreatedAt.nextToken;
          }
        } else if (useScorecard) {
          // If only a scorecard is selected, get items through ScorecardProcessedItem join table
          const directQuery = await graphqlRequest<{ 
            listScorecardProcessedItemByScorecardId: { 
              items: Array<{
                itemId: string;
                processedAt?: string;
                item: {
                  id: string;
                  externalId?: string;
                  description?: string;
                  accountId: string;
                  evaluationId?: string;
                  updatedAt?: string;
                  createdAt?: string;
                  isEvaluation: boolean;
                };
              }>;
              nextToken: string | null;
            }
          }>(`
            query ListItemsMoreDirect($scorecardId: ID!, $limit: Int!, $nextToken: String) {
              listScorecardProcessedItemByScorecardId(
                scorecardId: $scorecardId,
                limit: $limit,
                nextToken: $nextToken
              ) {
                items {
                  itemId
                  processedAt
                  item {
                    id
                    externalId
                    description
                    accountId
                    evaluationId
                    updatedAt
                    createdAt
                    isEvaluation
                    identifiers
                    itemIdentifiers {
                      items {
                        id
                        name
                        value
                        url
                        position
                      }
                    }
                  }
                }
                nextToken
              }
            }
          `, {
            scorecardId: selectedScorecard,
            limit: 100,
            nextToken: nextToken
          });
          
          if (directQuery.data?.listScorecardProcessedItemByScorecardId?.items) {
            // Extract items and sort by createdAt in descending order (most recent first)
            itemsFromDirectQuery = directQuery.data.listScorecardProcessedItemByScorecardId.items
              .map(association => association.item)
              .filter(item => item !== null)
              .sort((a, b) => {
                // Sort by createdAt (newest first)
                const dateA = new Date(a.createdAt || '').getTime();
                const dateB = new Date(b.createdAt || '').getTime();
                return dateB - dateA; // DESC order (newest first)
              });
            nextTokenFromDirectQuery = directQuery.data.listScorecardProcessedItemByScorecardId.nextToken;
          }
        } else {
          // If neither scorecard nor score is selected, filter by accountId
          const directQuery = await graphqlRequest<{ listItemByAccountIdAndCreatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsMoreDirect($accountId: String!, $limit: Int!, $nextToken: String) {
              listItemByAccountIdAndCreatedAt(
                accountId: $accountId, 
                sortDirection: DESC,
                limit: $limit,
                nextToken: $nextToken
              ) {
                items {
                  id
                  externalId
                  description
                  accountId
                  evaluationId
                  updatedAt
                  createdAt
                  isEvaluation
                  identifiers
                  itemIdentifiers {
                    items {
                      id
                      name
                      value
                      url
                      position
                    }
                  }
                }
                nextToken
              }
            }
          `, {
            accountId: selectedAccount.id,
            limit: 100,
            nextToken: nextToken
          });
          
          if (directQuery.data?.listItemByAccountIdAndCreatedAt?.items) {
            // No need to sort as the GSI already returns items sorted by createdAt
            itemsFromDirectQuery = directQuery.data.listItemByAccountIdAndCreatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByAccountIdAndCreatedAt.nextToken;
          }
        }
      } catch (error) {
        console.error('Error loading more items:', error);
      }
      
      // Use the items from the direct query
      const itemsToUse = itemsFromDirectQuery;
      const nextTokenToUse = nextTokenFromDirectQuery;
      
      
      // Transform the data to match the expected format
      const transformedItems = itemsToUse.map(item => transformItem(item, { isNew: false }));
      
      // Append the new items to the existing items
      setItems(prevItems => [...prevItems, ...transformedItems]);
      setNextToken(nextTokenToUse);
      
      // Don't clear isNew for "load more" - items are already set to isNew: false
    } catch (error) {
      console.error("Error fetching more items:", error);
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, nextToken, selectedAccount, selectedScorecard, selectedScore, setItems, setNextToken, setIsLoadingMore]);

  // Fetch items from the API
  const fetchItems = useCallback(async () => {
    console.log('🔍 FETCHING ITEMS', {
      timestamp: new Date().toISOString(),
      hasUser: !!user,
      selectedAccount: selectedAccount ? { id: selectedAccount.id, name: selectedAccount.name } : null,
      selectedScorecard,
      selectedScore
    });
    
    if (!user) {
      console.log('❌ User not authenticated, skipping item fetch');
      return;
    }
    
    if (!selectedAccount) {
      console.log('❌ No account selected in context, skipping item fetch');
      return;
    }
    
    setIsLoading(true);
    
    try {
      // Use the account ID from the context
      const accountId = selectedAccount.id;
      console.log('📋 Using account ID:', accountId);
      
      // Skip the amplifyClient.Item.list() call and only use the direct GraphQL query approach
      let itemsFromDirectQuery: any[] = [];
      let nextTokenFromDirectQuery: string | null = null;
      
      try {
        // Determine if we should filter by scorecard, score, or account
        const useScorecard = selectedScorecard !== null && selectedScorecard !== undefined;
        const useScore = selectedScore !== null && selectedScore !== undefined;
        
        console.log('🔍 Query filters:', { useScorecard, useScore, selectedScorecard, selectedScore });
        
        if (useScore) {
          console.log('📊 Fetching items by score ID:', selectedScore);
          // If a score is selected, filter by scoreId
          const directQuery = await graphqlRequest<{ listItemByScoreIdAndCreatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsDirect($scoreId: String!, $limit: Int!) {
              listItemByScoreIdAndCreatedAt(
                scoreId: $scoreId, 
                sortDirection: DESC,
                limit: $limit
              ) {
                items {
                  id
                  externalId
                  description
                  accountId
                  evaluationId
                  updatedAt
                  createdAt
                  isEvaluation
                  identifiers
                  itemIdentifiers {
                    items {
                      id
                      name
                      value
                      url
                      position
                    }
                  }
                }
                nextToken
              }
            }
          `, {
            scoreId: selectedScore,
            limit: 100
          });
          
          if (directQuery.data?.listItemByScoreIdAndCreatedAt?.items) {
            itemsFromDirectQuery = directQuery.data.listItemByScoreIdAndCreatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByScoreIdAndCreatedAt.nextToken;
            console.log('✅ Fetched items by score:', {
              count: itemsFromDirectQuery.length,
              hasNextToken: !!nextTokenFromDirectQuery
            });
          }
        } else if (useScorecard) {
          console.log('📊 Fetching items by scorecard ID:', selectedScorecard);
          // If only a scorecard is selected, get items through ScorecardProcessedItem join table
          const directQuery = await graphqlRequest<{ 
            listScorecardProcessedItemByScorecardId: { 
              items: Array<{
                itemId: string;
                processedAt?: string;
                item: {
                  id: string;
                  externalId?: string;
                  description?: string;
                  accountId: string;
                  evaluationId?: string;
                  updatedAt?: string;
                  createdAt?: string;
                  isEvaluation: boolean;
                };
              }>;
              nextToken: string | null;
            }
          }>(`
            query ListItemsDirect($scorecardId: ID!, $limit: Int!) {
              listScorecardProcessedItemByScorecardId(
                scorecardId: $scorecardId,
                limit: $limit
              ) {
                items {
                  itemId
                  processedAt
                  item {
                    id
                    externalId
                    description
                    accountId
                    evaluationId
                    updatedAt
                    createdAt
                    isEvaluation
                    identifiers
                    itemIdentifiers {
                      items {
                        id
                        name
                        value
                        url
                        position
                      }
                    }
                  }
                }
                nextToken
              }
            }
          `, {
            scorecardId: selectedScorecard,
            limit: 100
          });
          
          if (directQuery.data?.listScorecardProcessedItemByScorecardId?.items) {
            itemsFromDirectQuery = directQuery.data.listScorecardProcessedItemByScorecardId.items
              .map(association => association.item)
              .filter(item => item !== null)
              .sort((a, b) => {
                const dateA = new Date(a.createdAt || '').getTime();
                const dateB = new Date(b.createdAt || '').getTime();
                return dateB - dateA; // DESC order (newest first)
              });
            nextTokenFromDirectQuery = directQuery.data.listScorecardProcessedItemByScorecardId.nextToken;
            console.log('✅ Fetched items by scorecard:', {
              count: itemsFromDirectQuery.length,
              hasNextToken: !!nextTokenFromDirectQuery
            });
          }
        } else {
          console.log('📊 Fetching items by account ID:', accountId);
          // If neither scorecard nor score is selected, filter by accountId
          const directQuery = await graphqlRequest<{ listItemByAccountIdAndCreatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsDirect($accountId: String!, $limit: Int!) {
              listItemByAccountIdAndCreatedAt(
                accountId: $accountId, 
                sortDirection: DESC,
                limit: $limit
              ) {
                items {
                  id
                  externalId
                  description
                  accountId
                  evaluationId
                  updatedAt
                  createdAt
                  isEvaluation
                  identifiers
                  itemIdentifiers {
                    items {
                      id
                      name
                      value
                      url
                      position
                    }
                  }
                }
                nextToken
              }
            }
          `, {
            accountId: accountId,
            limit: 100
          });
          
          if (directQuery.data?.listItemByAccountIdAndCreatedAt?.items) {
            itemsFromDirectQuery = directQuery.data.listItemByAccountIdAndCreatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByAccountIdAndCreatedAt.nextToken;
            console.log('✅ Fetched items by account:', {
              count: itemsFromDirectQuery.length,
              hasNextToken: !!nextTokenFromDirectQuery,
              firstItem: itemsFromDirectQuery[0] ? {
                id: itemsFromDirectQuery[0].id,
                externalId: itemsFromDirectQuery[0].externalId,
                createdAt: itemsFromDirectQuery[0].createdAt
              } : null
            });
          }
        }
      } catch (error) {
        console.error('❌ Error in GraphQL query:', error);
      }
      
      const itemsToUse = itemsFromDirectQuery;
      const nextTokenToUse = nextTokenFromDirectQuery;
      
      if (itemsToUse.length === 0) {
        console.log('⚠️ No items found for this account. You may need to create some items first.');
      } else {
        console.log('📊 Processing items:', {
          totalCount: itemsToUse.length,
          accountIds: [...new Set(itemsToUse.map(item => item.accountId))]
        });
      }
      
      const transformedItems = itemsToUse.map(item => transformItem(item, { isNew: false }));
      
      console.log('✅ Setting items state:', {
        count: transformedItems.length,
        nextToken: nextTokenToUse
      });
      
      setItems(transformedItems);
      setNextToken(nextTokenToUse);
      
      // Don't clear isNew for initial load - items are already set to isNew: false
      
      setIsLoading(false);
      console.log('✅ Item fetch complete');
    } catch (error) {
      console.error('❌ Error fetching items:', error);
      setIsLoading(false);
    }
  }, [user, selectedAccount, setIsLoading, setItems, setNextToken, selectedScorecard, selectedScore]);
  
  // Throttled refetch function for when we get empty update notifications
  const throttledRefetch = useCallback(async () => {
    // Clear any existing timeout
    if (refetchTimeoutRef.current) {
      clearTimeout(refetchTimeoutRef.current);
    }
    
    // Set a new timeout to refetch after 2 seconds of no new notifications
    refetchTimeoutRef.current = setTimeout(async () => {
      if (!selectedAccount) return;
      
      try {
        // Fetch fresh data without clearing the existing items
        const accountId = selectedAccount.id;
        let itemsFromDirectQuery: any[] = [];
        
        // Use the same query logic as fetchItems but without clearing state
        const useScorecard = selectedScorecard !== null && selectedScorecard !== undefined;
        const useScore = selectedScore !== null && selectedScore !== undefined;
        
        if (useScore) {
          const directQuery = await graphqlRequest<{ listItemByScoreIdAndCreatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsDirect($scoreId: String!, $limit: Int!) {
              listItemByScoreIdAndCreatedAt(
                scoreId: $scoreId, 
                sortDirection: DESC,
                limit: $limit
              ) {
                items {
                  id
                  externalId
                  description
                  accountId
                  evaluationId
                  updatedAt
                  createdAt
                  isEvaluation
                  identifiers
                  itemIdentifiers {
                    items {
                      id
                      name
                      value
                      url
                      position
                    }
                  }
                }
                nextToken
              }
            }
          `, {
            scoreId: selectedScore,
            limit: 100
          });
          itemsFromDirectQuery = directQuery.data?.listItemByScoreIdAndCreatedAt?.items || [];
        } else if (useScorecard) {
          const directQuery = await graphqlRequest<{ 
            listScorecardProcessedItemByScorecardId: { 
              items: Array<{
                itemId: string;
                processedAt?: string;
                item: any;
              }>;
              nextToken: string | null;
            }
          }>(`
            query ListItemsDirect($scorecardId: ID!, $limit: Int!) {
              listScorecardProcessedItemByScorecardId(
                scorecardId: $scorecardId,
                limit: $limit
              ) {
                items {
                  itemId
                  processedAt
                  item {
                    id
                    externalId
                    description
                    accountId
                    evaluationId
                    updatedAt
                    createdAt
                    isEvaluation
                    identifiers
                    itemIdentifiers {
                      items {
                        id
                        name
                        value
                        url
                        position
                      }
                    }
                  }
                }
                nextToken
              }
            }
          `, {
            scorecardId: selectedScorecard,
            limit: 100
          });
          itemsFromDirectQuery = directQuery.data?.listScorecardProcessedItemByScorecardId?.items
            ?.map(association => association.item)
            ?.filter(item => item !== null)
            ?.sort((a, b) => {
              const dateA = new Date(a.createdAt || '').getTime();
              const dateB = new Date(b.createdAt || '').getTime();
              return dateB - dateA;
            }) || [];
        } else {
          const directQuery = await graphqlRequest<{ listItemByAccountIdAndCreatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsDirect($accountId: String!, $limit: Int!) {
              listItemByAccountIdAndCreatedAt(
                accountId: $accountId, 
                sortDirection: DESC,
                limit: $limit
              ) {
                items {
                  id
                  externalId
                  description
                  accountId
                  evaluationId
                  updatedAt
                  createdAt
                  isEvaluation
                  identifiers
                  itemIdentifiers {
                    items {
                      id
                      name
                      value
                      url
                      position
                    }
                  }
                }
                nextToken
              }
            }
          `, {
            accountId: accountId,
            limit: 100
          });
          itemsFromDirectQuery = directQuery.data?.listItemByAccountIdAndCreatedAt?.items || [];
        }
        
        // Transform and merge with existing items
        const transformedItems = itemsFromDirectQuery.map(item => transformItem(item, { isNew: false }));
        
        // Merge with existing items - update existing ones and add new ones
        setItems(prevItems => {
          const existingIds = new Set(prevItems.map(item => item.id));
          const newItems = transformedItems
            .filter(item => !existingIds.has(item.id))
            .map(newItem => {
              console.log('🎯 NEW ITEM FOUND IN THROTTLED REFETCH:', {
                id: newItem.id,
                externalId: newItem.externalId,
                source: 'throttledRefetch'
              });
              return { ...newItem, isNew: true }; // Mark new items as new!
            });
          
          // Update existing items and add new ones at the beginning
          const updatedItems = prevItems.map(prevItem => {
            const freshItem = transformedItems.find(item => item.id === prevItem.id);
            return freshItem ? { ...prevItem, ...freshItem, isNew: prevItem.isNew } : prevItem; // Preserve isNew status for existing items
          });
          
          // Add timeout to clear isNew flag for the new items found in refetch
          if (newItems.length > 0) {
            setTimeout(() => {
              setItems(currentItems => 
                currentItems.map(item => 
                  newItems.some(newItem => newItem.id === item.id) 
                    ? { ...item, isNew: false }
                    : item
                )
              );
            }, 3000);
          }
          
          return [...newItems, ...updatedItems];
        });
        
      } catch (error) {
        console.error('Error during throttled refetch:', error);
      }
    }, 2000); // 2 second debounce
  }, [selectedAccount, selectedScorecard, selectedScore]);
  
  // Ref to track when we need to refetch items
  const shouldRefetchRef = useRef(false);
  
  // Mark when we need to refetch due to filter changes
  useEffect(() => {
    if (!isLoadingAccounts && selectedAccount) {
      shouldRefetchRef.current = true;
    }
  }, [selectedAccount, isLoadingAccounts, selectedScorecard, selectedScore]);
  
  // Fetch items when the selected account or other filters change
  useEffect(() => {
    if (!isLoadingAccounts && selectedAccount && shouldRefetchRef.current) {
      shouldRefetchRef.current = false; // Reset the flag
      
      // Reset items and nextToken when filters change, but preserve specifically fetched items
      setItems(prevItems => {
        // Keep any items that were specifically fetched (not from the main list)
        const specificItem = params.id ? prevItems.find(item => item.id === params.id) : null;
        console.log('🔄 Main fetch useEffect - preserving specific item:', {
          paramsId: params.id,
          foundSpecificItem: !!specificItem,
          prevItemsCount: prevItems.length,
          specificItemId: specificItem?.id
        });
        return specificItem ? [specificItem] : [];
      });
      setNextToken(null);
      fetchItems();
    } else if (!isLoadingAccounts && !selectedAccount) {
      setItems([]); // Ensure items are cleared
      setNextToken(null);
      setIsLoading(false); // Stop loading indicator
    }
  }, [fetchItems, selectedAccount, isLoadingAccounts, params.id, setItems, setNextToken]);

  // Initialize score count manager
  useEffect(() => {
    if (!scoreCountManagerRef.current) {
      scoreCountManagerRef.current = new ScoreResultCountManager();
      
      // Subscribe to count changes with better state management
      const unsubscribe = scoreCountManagerRef.current.subscribe((counts) => {
        console.log('📊 Score count manager update:', counts);
        
        // Only update state if counts have actually changed
        setScoreResultCounts(prevCounts => {
          // Check if the new counts Map is actually different from the previous one
          if (prevCounts.size !== counts.size) {
            return counts;
          }
          
          // Check if any individual counts have changed
          let hasChanges = false;
          for (const [itemId, newCount] of counts) {
            const prevCount = prevCounts.get(itemId);
            if (!prevCount || 
                prevCount.count !== newCount.count || 
                prevCount.isLoading !== newCount.isLoading ||
                JSON.stringify(prevCount.scorecardBreakdown) !== JSON.stringify(newCount.scorecardBreakdown)) {
              hasChanges = true;
              break;
            }
          }
          
          return hasChanges ? counts : prevCounts;
        });
      });
      
      return () => {
        unsubscribe();
        if (scoreCountManagerRef.current) {
          scoreCountManagerRef.current.destroy();
          scoreCountManagerRef.current = null;
        }
      };
    }
  }, []);

  // Set up subscriptions for item creations and updates
  useEffect(() => {
    console.log('🔍 SUBSCRIPTION SETUP CHECK:', {
      selectedAccount: selectedAccount ? { id: selectedAccount.id, name: selectedAccount.name } : null,
      isLoadingAccounts,
      willSetupSubscriptions: !(!selectedAccount || isLoadingAccounts)
    });
    
    if (!selectedAccount || isLoadingAccounts) return; // Also wait for accounts to be loaded
    
    console.log('🔄 SETTING UP SUBSCRIPTIONS', {
      accountId: selectedAccount.id,
      accountName: selectedAccount.name,
      timestamp: new Date().toISOString()
    });
    
    // Item creation subscription
    const createSubscription = observeItemCreations().subscribe({
      next: async ({ data: newItem }) => {
        if (!newItem) {
          return;
        }
        
        if (newItem.accountId === selectedAccount.id) {
          // Transform the new item to match our expected format
          const transformedNewItem = transformItem(newItem, { isNew: true });

          // Add the new item to the TOP of the list
          setItems(prevItems => [transformedNewItem, ...prevItems]);
          
          // Show a toast notification that new items are being loaded
          toast.success('🎉 New item detected! Refreshing...', {
            duration: 3000,
          });
          
          // After 3 seconds, remove the "New" status and make it look normal
          setTimeout(() => {
            setItems(prevItems => 
              prevItems.map(item => 
                item.id === newItem.id 
                  ? { ...item, status: "Done", isNew: false }
                  : item
              )
            );
          }, 3000);
        }
      },
      error: (error) => {
        console.error('❌ Item creation subscription error:', {
          error,
          message: error?.message,
          stack: error?.stack
        });
        toast.error("Error in item subscription.");
      }
    });
    
    console.log('✅ Item creation subscription set up');
    
    // Item update subscription
    const updateSubscription = observeItemUpdates().subscribe({
      next: async ({ data: updatedItem, needsRefetch }) => {
        console.log('📥 ITEM UPDATE EVENT RECEIVED', {
          timestamp: new Date().toISOString(),
          updatedItem,
          needsRefetch,
          hasData: !!updatedItem,
          accountMatch: updatedItem?.accountId === selectedAccount.id
        });
        
        // Handle empty notifications that require a refetch
        if (needsRefetch && !updatedItem) {
          console.log('🔄 Empty update notification - triggering refetch');
          throttledRefetch();
          return;
        }
        
        if (!updatedItem) {
          console.warn('📥 Empty item update event received without refetch flag');
          return;
        }
        
        if (updatedItem.accountId === selectedAccount.id) {
          console.log('✅ Processing updated item for current account', {
            itemId: updatedItem.id,
            externalId: updatedItem.externalId
            // Removed currentItemCount and itemExists to avoid stale closure
          });
          
          // Update the item in the list if it exists
          setItems(prevItems => {
            const updatedItems = prevItems.map(item => 
              item.id === updatedItem.id 
                ? {
                    ...item,
                    externalId: updatedItem.externalId,
                    description: updatedItem.description,
                    updatedAt: updatedItem.updatedAt,
                    // Keep createdAt and date as they were (don't change sort order)
                  }
                : item
            );
            
            const wasUpdated = updatedItems !== prevItems;
            console.log('📝 Updated items state', {
              wasUpdated,
              itemFound: wasUpdated
            });
            
            return updatedItems;
          });
          
          // Trigger a re-count of score results for this item
          if (scoreCountManagerRef.current) {
            console.log('📊 Clearing and reloading count for updated item:', updatedItem.id);
            scoreCountManagerRef.current.clearCount(updatedItem.id);
            scoreCountManagerRef.current.loadCountForItem(updatedItem.id);
          }
        } else {
          console.log('🚫 Updated item is for different account', {
            itemAccountId: updatedItem.accountId,
            currentAccountId: selectedAccount.id
          });
        }
      },
      error: (error) => {
        console.error('❌ Item update subscription error:', {
          error,
          message: error?.message,
          stack: error?.stack
        });
        toast.error("Error in item update subscription.");
      }
    });
    
    console.log('✅ Item update subscription set up');
    
    // Score result subscription
    const scoreResultSubscription = observeScoreResultChanges().subscribe({
      next: async ({ data: changeEvent }) => {
        console.log('📊 Score result subscription received:', {
          timestamp: new Date().toISOString(),
          changeEvent,
          hasData: !!changeEvent
        });
        
        if (!changeEvent) {
          console.log('📊 Empty score result notification');
          return;
        }
        
        try {
          console.log('📊 Score result change detected, action:', changeEvent.action);
          
          // Since we can't reliably parse the subscription data, refresh all cached counts
          // This is more aggressive but ensures consistency
          if (scoreCountManagerRef.current) {
            console.log('📊 Refreshing all cached score counts due to score result change');
            scoreCountManagerRef.current.refreshAllCounts();
          } else {
            console.log('📊 ScoreCountManager not available');
          }
        } catch (error) {
          console.error('📊 Error handling score result change:', error);
        }
      },
      error: (error) => {
        console.error('❌ Score result subscription error:', {
          error,
          message: error?.message,
          stack: error?.stack
        });
        toast.error("Error in score result subscription.");
      }
    });
    
    console.log('✅ Score result subscription set up');
    
    itemSubscriptionRef.current = createSubscription;
    itemUpdateSubscriptionRef.current = updateSubscription;
    scoreResultSubscriptionRef.current = scoreResultSubscription;
    
    console.log('✅ ALL SUBSCRIPTIONS SET UP SUCCESSFULLY');
    
    return () => {
      console.log('🧹 CLEANING UP SUBSCRIPTIONS');
      if (itemSubscriptionRef.current) {
        itemSubscriptionRef.current.unsubscribe();
        itemSubscriptionRef.current = null;
      }
      if (itemUpdateSubscriptionRef.current) {
        itemUpdateSubscriptionRef.current.unsubscribe();
        itemUpdateSubscriptionRef.current = null;
      }
      if (scoreResultSubscriptionRef.current) {
        scoreResultSubscriptionRef.current.unsubscribe();
        scoreResultSubscriptionRef.current = null;
      }
      // Clear any pending refetch timeout
      if (refetchTimeoutRef.current) {
        clearTimeout(refetchTimeoutRef.current);
        refetchTimeoutRef.current = null;
      }
    };
  }, [selectedAccount, isLoadingAccounts, throttledRefetch]); // Removed fetchItems, added throttledRefetch which is actually used

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
      if (!selectedScorecard && !selectedScore && filterConfig.length === 0) return true
      
      // Check for scorecard and score matches using groupedScoreResults
      let scorecardMatch = !selectedScorecard || (item.groupedScoreResults && Object.keys(item.groupedScoreResults).includes(selectedScorecard))
      let scoreMatch = !selectedScore || (item.groupedScoreResults && Object.values(item.groupedScoreResults).some(scorecard => 
        scorecard.scores.some(score => score.scoreId === selectedScore)
      ))
      
      if (filterConfig.length === 0) return scorecardMatch && scoreMatch
      
      return scorecardMatch && scoreMatch && filterConfig.some(group => {
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
  }, [selectedScorecard, selectedScore, filterConfig, items])

  const getBadgeVariant = (status: string) => {
    switch (status) {
      case 'New':
        return 'bg-gradient-to-r from-green-400 to-green-600 text-white h-6 animate-pulse shadow-lg shadow-green-400/50';
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

  const toggleExplanation = React.useCallback((scoreName: string) => {
    setExpandedExplanations(prev => 
      prev.includes(scoreName) 
        ? prev.filter(name => name !== scoreName)
        : [...prev, scoreName]
    );
  }, []);

  const toggleAnnotations = React.useCallback((scoreName: string) => {
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

  const setExplanationRef = React.useCallback((element: HTMLDivElement | null, scoreName: string) => {
    if (element) {
      explanationRefs.current[scoreName] = element;
    }
  }, []);

  const renderSelectedItem = () => {
    console.log('🎨 renderSelectedItem called:', { 
      selectedItem, 
      itemsCount: items.length,
      isLoading,
      specificItemLoading,
      hasSelectedAccount: !!selectedAccount,
      isLoadingAccounts
    });
    
    if (!selectedItem) {
      console.log('❌ No selected item, returning null');
      return null
    }

    // If accounts are still loading, show loading state
    if (isLoadingAccounts) {
      console.log('⏳ Accounts still loading, showing loading state');
      return (
        <div className="h-full flex flex-col">
          <div className="flex-1 flex items-center justify-center">
            <div className="flex items-center space-x-2">
              <Loader2 className="h-6 w-6 animate-spin" />
              <span>Loading item details...</span>
            </div>
          </div>
        </div>
      )
    }

    const selectedItemData = items.find(item => item.id === selectedItem)
    console.log('🔍 selectedItemData found:', !!selectedItemData);
    
    const scoreCount = scoreResultCounts.get(selectedItem)
    const selectedItemWithCount = selectedItemData ? {
      ...selectedItemData,
      results: scoreCount?.count || selectedItemData.results,
      isLoadingResults: scoreCount?.isLoading || false,
      scorecardBreakdown: scoreCount?.scorecardBreakdown || undefined
    } : null
    
    console.log('📊 selectedItemWithCount created:', !!selectedItemWithCount);
    
    // If item is not found, check if we should attempt to fetch it or if we're already loading
    if (!selectedItemWithCount) {
      console.log('❗ selectedItemWithCount is null, checking loading states');
      
      // ALWAYS check loading states first - this takes precedence over failed fetches
      // because fetchSpecificItem may be retrying a previously failed item
      if (isLoading || specificItemLoading) {
        console.log('⏳ Showing loading (isLoading:', isLoading, 'specificItemLoading:', specificItemLoading, ')');
        return (
          <div className="h-full flex flex-col">
            <div className="flex-1 flex items-center justify-center">
              <div className="flex items-center space-x-2">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span>Loading item details...</span>
              </div>
            </div>
          </div>
        )
      }
      
      // Only check failed fetches if we're not currently loading
      if (failedItemFetches.has(selectedItem)) {
        console.log('❌ Item fetch already failed, showing error');
        return (
          <div className="h-full flex flex-col">
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <p className="text-muted-foreground mb-2">Item not found</p>
                <p className="text-sm text-muted-foreground">
                  The item with ID {selectedItem} could not be found.
                </p>
              </div>
            </div>
          </div>
        )
      }
      
      // If we have a selected account and the item truly doesn't exist,
      // show an appropriate error message
      if (selectedAccount) {
        console.log('🚫 Item not found with selected account, showing error');
        return (
          <div className="h-full flex flex-col">
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <p className="text-muted-foreground mb-2">Item not found</p>
                <p className="text-sm text-muted-foreground">
                  The item with ID {selectedItem} could not be found.
                </p>
              </div>
            </div>
          </div>
        )
      }
      
      console.log('🚫 No selected account, returning null');
      // Only show not found if we have no account (shouldn't happen) 
      // or we've definitively determined the item doesn't exist
      return null
    }

    console.log('✅ Rendering ItemCard for selected item');

    
    return (
      <div className="h-full flex flex-col">
        <div className="flex-1 overflow-auto">
          <ItemCard
            key={selectedItem} // Force re-render when selectedItem changes
            variant="detail"
            item={selectedItemWithCount as ItemData}
            getBadgeVariant={getBadgeVariant}
            isFullWidth={isFullWidth}
            onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
            onClose={() => {
              debugSetSelectedItem(null);
              setIsFullWidth(false);
              // Update URL using browser History API to avoid Next.js navigation
              window.history.replaceState(null, '', `/lab/items`)
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
                className={`text-sm text-muted-foreground overflow-hidden cursor-pointer ${expandedExplanations.includes(score.name) ? '' : ''}`}
                onClick={() => toggleExplanation(score.name)}
              >
                {renderRichText(score.explanation)}
              </div>
              {showExpandButton[score.name] && (
                <Button 
                  variant="link" 
                  size="sm" 
                  onClick={() => toggleExplanation(score.name)}
                  className="px-0 py-1 h-auto text-xs mt-1"
                >
                  {expandedExplanations.includes(score.name) ? (
                    <>Show less <ChevronUp className="h-3 w-3 inline ml-1" /></>
                  ) : (
                    <>Show more <ChevronDown className="h-3 w-3 inline ml-1" /></>
                  )}
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
            <div 
              className={`text-sm text-muted-foreground overflow-hidden cursor-pointer ${expandedExplanations.includes(score.name) ? '' : ''}`}
              onClick={() => toggleExplanation(score.name)}
            >
              {renderRichText(score.explanation)}
            </div>
            {showExpandButton[score.name] && (
              <Button 
                variant="link" 
                size="sm" 
                onClick={() => toggleExplanation(score.name)}
                className="px-0 py-1 h-auto text-xs mt-1"
              >
                {expandedExplanations.includes(score.name) ? (
                  <>Show less <ChevronUp className="h-3 w-3 inline ml-1" /></>
                ) : (
                  <>Show more <ChevronDown className="h-3 w-3 inline ml-1" /></>
                )}
              </Button>
            )}
          </>
        )}
      </div>
    );
  }

  const handleItemClick = (itemId: string) => {
    // Update URL using browser History API to avoid Next.js navigation
    const newUrl = `/lab/items/${itemId}`
    window.history.replaceState(null, '', newUrl)
    
    // Update state - the deep-linking useEffect will handle the rest
    debugSetSelectedItem(itemId)
    
    // For items in the grid (first page), ensure we can scroll to them
    if (items.some(item => item.id === itemId)) {
      // Item is in first page - ensure grid view and scroll to item
      if (!isNarrowViewport) {
        setIsFullWidth(false)
      }
      
      // Scroll to the selected item with retry logic
      scrollToSelectedItem(itemId);
    } else {
      // Item not in first page - will be handled by deep-linking useEffect
      console.log('🔄 Item not in first page, deep-linking useEffect will handle');
    }
    
    // Handle narrow viewport
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

  // Add a useEffect for the intersection observer
  useEffect(() => {
    // Don't set up observer if we don't have items or a next token
    if (!nextToken || filteredItems.length === 0) {
      return;
    }

    // Create the intersection observer
    const options = {
      root: null, // Use the viewport as the root
      rootMargin: '0px 0px 200px 0px', // Start loading when user is 200px from the bottom
      threshold: 0.1 // Trigger when 10% of the target is visible
    };

    const handleObserver = (entries: IntersectionObserverEntry[]) => {
      const [entry] = entries;
      if (entry.isIntersecting && nextToken && !isLoadingMore) {
        handleLoadMore();
      }
    };

    // Initialize the observer
    observerRef.current = new IntersectionObserver(handleObserver, options);
    
    // Use a timeout to ensure the DOM has updated before observing
    const timeoutId = setTimeout(() => {
      if (loadMoreRef.current && observerRef.current) {
        observerRef.current.observe(loadMoreRef.current);
      }
    }, 0);

    // Cleanup
    return () => {
      clearTimeout(timeoutId);
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [nextToken, isLoadingMore, handleLoadMore, filteredItems.length]); // Add filteredItems.length to ensure observer resets when items change

  // Cleanup search error timeout on unmount
  useEffect(() => {
    return () => {
      if (searchErrorTimeoutRef.current) {
        clearTimeout(searchErrorTimeoutRef.current);
      }
    };
  }, []);

  // Show loading skeleton for initial load
  if (isLoading && items.length === 0) {
    return <ItemsDashboardSkeleton />
  }

  return (
    <div className="flex flex-col h-full p-1.5">
      <div className="flex items-center justify-between pb-3">
        <div className="flex items-center space-x-4">
          <div className="flex-grow">
            <ScorecardContext 
              selectedScorecard={selectedScorecard}
              setSelectedScorecard={setSelectedScorecard}
              selectedScore={selectedScore}
              setSelectedScore={setSelectedScore}
              availableFields={availableFields}
              timeRangeOptions={scoreOptions}
              skeletonMode={isLoading}
            />
          </div>
        </div>
        
        {/* Search Component */}
        <div className="flex items-center relative">
          <form onSubmit={handleSearchSubmit} className="relative">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-4 w-4 text-muted-foreground" />
              </div>
              <Input
                type="text"
                placeholder="Search by identifier"
                value={searchValue}
                onChange={(e) => {
                  setSearchValue(e.target.value);
                  if (searchError) setSearchError(null); // Clear error when typing
                }}
                className={`w-[200px] h-9 pl-10 ${searchValue.trim() ? 'pr-20' : 'pr-3'} bg-card border-0 shadow-none focus:ring-0 focus:ring-offset-0 focus:outline-none focus:border-0 focus:shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:outline-none`}
                disabled={isSearching}
              />
              {searchValue.trim() && (
                <Button 
                  type="submit" 
                  size="sm" 
                  className="absolute inset-y-0 right-0 h-9 px-3 rounded-l-none shadow-none"
                  disabled={isSearching}
                >
                  {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Search'}
                </Button>
              )}
            </div>
          </form>
          
          {/* Error message */}
          {searchError && (
            <div className="absolute top-full mt-2 right-0 z-50 bg-muted text-muted-foreground text-sm px-3 py-2 rounded-md shadow-sm min-w-[200px] border border-border">
              {searchError}
            </div>
          )}
        </div>
      </div>
      
      <div className="flex-grow flex flex-col overflow-hidden">
        {/* 
          Deep-linking rendering logic:
          1. Full-width mode: When item is NOT in first page (isFullWidth=true) or narrow viewport
          2. Split view: When item IS in first page (isFullWidth=false) 
          3. Grid-only: When no item is selected
        */}
        {selectedItem && (isNarrowViewport || isFullWidth) ? (
          <div className="flex-grow overflow-hidden">
            {renderSelectedItem()}
          </div>
        ) : selectedItem ? (
          // Show split view when item is selected but not narrow viewport or full width
          <div className={`flex ${isNarrowViewport ? 'flex-col' : ''} h-full`}>
            <div 
              className={`${isFullWidth ? 'hidden' : 'flex-1'} overflow-auto`}
              style={selectedItem && !isNarrowViewport && !isFullWidth ? {
                width: `${leftPanelWidth}%`
              } : undefined}
            >
              <div>
                <div className="@container h-full">
                  {filteredItems.length === 0 ? (
                    // Show skeleton instead of "No items found" message
                    <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 animate-pulse">
                      {[...Array(12)].map((_, i) => (
                        <ItemCardSkeleton key={i} />
                      ))}
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3">
                        {filteredItems.map((item) => {
                          const scoreCount = scoreResultCounts.get(item.id);
                          return (
                            <MemoizedGridItemCard
                              key={item.id}
                              item={item}
                              scoreCount={scoreCount}
                              selectedItem={selectedItem}
                              handleItemClick={handleItemClick}
                              getBadgeVariant={getBadgeVariant}
                              scoreCountManagerRef={scoreCountManagerRef}
                              itemRefsMap={itemRefsMap}
                            />
                          );
                        })}
                      </div>
                      
                      {/* Replace the Load More button with an invisible loading indicator */}
                      {nextToken && filteredItems.length > 0 && (
                        <div 
                          ref={loadMoreRef} 
                          className="flex justify-center py-6"
                        >
                          {isLoadingMore && (
                            <div className="flex items-center">
                              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                              <span>Loading more items...</span>
                            </div>
                          )}
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
        ) : (
          // Grid-only view when no item is selected
          <div className="h-full">
            <div className="overflow-auto h-full">
              <div>
                <div className="@container h-full">
                  {filteredItems.length === 0 ? (
                    // Show skeleton instead of "No items found" message
                    <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 animate-pulse">
                      {[...Array(12)].map((_, i) => (
                        <ItemCardSkeleton key={i} />
                      ))}
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3">
                        {filteredItems.map((item) => {
                          const scoreCount = scoreResultCounts.get(item.id);
                          return (
                            <MemoizedGridItemCard
                              key={item.id}
                              item={item}
                              scoreCount={scoreCount}
                              selectedItem={selectedItem}
                              handleItemClick={handleItemClick}
                              getBadgeVariant={getBadgeVariant}
                              scoreCountManagerRef={scoreCountManagerRef}
                              itemRefsMap={itemRefsMap}
                            />
                          );
                        })}
                      </div>
                      
                      {/* Replace the Load More button with an invisible loading indicator */}
                      {nextToken && filteredItems.length > 0 && (
                        <div 
                          ref={loadMoreRef} 
                          className="flex justify-center py-6"
                        >
                          {isLoadingMore && (
                            <div className="flex items-center">
                              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                              <span>Loading more items...</span>
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Suspense wrapper to fix build issues with useSearchParams
export default function ItemsDashboard() {
  return (
    <Suspense fallback={<ItemsDashboardSkeleton />}>
      <ItemsDashboardInner />
    </Suspense>
  );
}


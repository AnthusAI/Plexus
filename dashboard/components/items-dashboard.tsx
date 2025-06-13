"use client"
import React, { useContext, useEffect, useMemo, useRef, useState, useCallback, Suspense } from "react"
import { useSearchParams, useParams } from 'next/navigation'
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, Loader2, Search, AlertTriangle } from "lucide-react"
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
import ScoreResultCard, { ScoreResultData } from './items/ScoreResultCard'
import { amplifyClient, graphqlRequest } from '@/utils/amplify-client'
import { useAuthenticator } from '@aws-amplify/ui-react'
import { ScorecardContextProps } from "./ScorecardContext"
import { observeItemCreations, observeItemUpdates, observeScoreResultChanges } from '@/utils/subscriptions'
import { toast } from 'sonner'
import { useAccount } from '@/app/contexts/AccountContext'
import { ItemsDashboardSkeleton, ItemCardSkeleton } from './loading-skeleton'
import { ScoreResultCountManager, type ScoreResultCount } from '@/utils/score-result-counter'
import { motion, AnimatePresence } from 'framer-motion'
import { ItemsGauges } from './ItemsGauges'

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
  
  // UI fields for ItemCard
  metadata?: Record<string, string>;
  attachedFiles?: string[];
  text?: string;
  
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

// Memoized grid component to prevent re-renders when just selection changes
const GridContent = ({ 
  filteredItems,
  selectedItem,
  handleItemClick,
  getBadgeVariant,
  scoreCountManagerRef,
  itemRefsMap,
  scoreResultCounts,
  nextToken,
  isLoadingMore,
  loadMoreRef,
  isLoading,
  hasInitiallyLoaded,
  itemsWithErrors
}: {
  filteredItems: Item[];
  selectedItem: string | null;
  handleItemClick: (itemId: string) => void;
  getBadgeVariant: (status: string) => string;
  scoreCountManagerRef: React.MutableRefObject<ScoreResultCountManager | null>;
  itemRefsMap: React.MutableRefObject<Map<string, HTMLDivElement | null>>;
  scoreResultCounts: Map<string, ScoreResultCount>;
  nextToken: string | null;
  isLoadingMore: boolean;
  loadMoreRef: React.MutableRefObject<HTMLDivElement | null>;
  isLoading: boolean;
  hasInitiallyLoaded: boolean;
  itemsWithErrors: Set<string>;
}) => {
  // Only show "No items found" if we're not loading and have actually finished the initial load
  if (filteredItems.length === 0 && !isLoading && hasInitiallyLoaded) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        No items found
      </div>
    );
  }

  return (
    <>
      <motion.div 
        className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3"
        layout
      >
        <AnimatePresence mode="popLayout">
          {filteredItems.map((item) => {
            const scoreCount = scoreResultCounts.get(item.id);
            return (
              <GridItemCard
                key={item.id}
                item={item}
                scoreCount={scoreCount}
                selectedItem={selectedItem}
                handleItemClick={handleItemClick}
                getBadgeVariant={getBadgeVariant}
                scoreCountManagerRef={scoreCountManagerRef}
                itemRefsMap={itemRefsMap}
                itemsWithErrors={itemsWithErrors}
              />
            );
          })}
        </AnimatePresence>
      </motion.div>
      
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
  );
};

// Grid item component
const GridItemCard = ({ 
  item, 
  scoreCount, 
  selectedItem, 
  handleItemClick, 
  getBadgeVariant, 
  scoreCountManagerRef,
  itemRefsMap,
  itemsWithErrors
}: {
  item: Item;
  scoreCount: ScoreResultCount | undefined;
  selectedItem: string | null;
  handleItemClick: (itemId: string) => void;
  getBadgeVariant: (status: string) => string;
  scoreCountManagerRef: React.MutableRefObject<ScoreResultCountManager | null>;
  itemRefsMap: React.MutableRefObject<Map<string, HTMLDivElement | null>>;
  itemsWithErrors: Set<string>;
}) => {
  const itemWithCount = useMemo(() => ({
    ...item,
    results: scoreCount?.count || item.results,
    isLoadingResults: scoreCount?.isLoading ?? item.isLoadingResults,
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
    <motion.div
      layoutId={`item-${item.id}`}
      layout
      initial={item.isNew ? {} : { opacity: 0 }}
      animate={item.isNew ? {} : { opacity: 1 }}
      exit={{ 
        opacity: 0,
        transition: { duration: 0.2 }
      }}
      transition={{
        layout: {
          duration: 1.0,
          ease: "easeInOut"
        },
        opacity: { duration: 0.4 }
      }}
      className={item.isNew ? 'new-item-glow' : ''}
    >
      <ItemCard
        variant="grid"
        item={itemWithCount}
        isSelected={selectedItem === item.id}
        onClick={handleClick}
        getBadgeVariant={getBadgeVariant}
        readOnly={true}
        hasErrors={itemsWithErrors.has(item.id)}
        ref={combinedRef}
      />
    </motion.div>
  );
};

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
    
      return transformedIdentifiers;
}
  
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
    isLoadingResults: true, // Set to true initially since score results load separately
    
    // Metadata and file attachments (parse from item if available)
    metadata: item.metadata ? (typeof item.metadata === 'string' ? JSON.parse(item.metadata) : item.metadata) : {},
    attachedFiles: item.attachedFiles || [],
    text: item.text,
    
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
  const searchParams = useSearchParams()
  const params = useParams()
  const [selectedItem, setSelectedItem] = useState<string | null>(null)
  

  const [isFullWidth, setIsFullWidth] = useState(false)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [isMetadataExpanded, setIsMetadataExpanded] = useState(false)
  const [isDataExpanded, setIsDataExpanded] = useState(false)
  const [selectedScore, setSelectedScore] = useState<string | null>(null);
  const [isErrorFilterActive, setIsErrorFilterActive] = useState(false);
  const [itemsWithErrors, setItemsWithErrors] = useState<Set<string>>(new Set());
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
  const [items, setItemsState] = useState<Item[]>([]);
  
  // Simplified setItems wrapper
  const setItems = useCallback((itemsOrUpdater: Item[] | ((prevItems: Item[]) => Item[])) => {
    if (typeof itemsOrUpdater === 'function') {
      setItemsState(itemsOrUpdater);
    } else {
      setItemsState(itemsOrUpdater);
    }
  }, []);
  const [sampleMethod, setSampleMethod] = useState("All");
  const [sampleCount, setSampleCount] = useState(100);
  const [scoreResults, setScoreResults] = useState(sampleScoreResults);
  const [leftPanelWidth, setLeftPanelWidth] = useState(50);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [nextToken, setNextToken] = useState<string | null>(null);
  const [hasInitiallyLoaded, setHasInitiallyLoaded] = useState(false);
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
  const scoreCountRefetchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [specificallyFetchedItems, setSpecificallyFetchedItems] = useState<Set<string>>(new Set());
  
  // Ref map to track item elements for scroll-to-view functionality
  const itemRefsMap = useRef<Map<string, HTMLDivElement | null>>(new Map());
  
  // Ref to hold the refetch function for the currently selected item's score results
  const scoreResultsRefetchRef = useRef<(() => void) | null>(null);

  // Wake-from-sleep detection state
  const pageHiddenTimeRef = useRef<number | null>(null);
  const isPageVisibleRef = useRef<boolean>(!document.hidden);
  const WAKE_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes

  // Search state
  const [searchValue, setSearchValue] = useState<string>('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const searchErrorTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // Score result selection state
  const [selectedScoreResult, setSelectedScoreResult] = useState<ScoreResultData | null>(null);
  
  // Handler for score result selection
  const handleScoreResultSelect = useCallback((scoreResult: any) => {
    setSelectedScoreResult(scoreResult);
  }, []);
  
  // Clear selected score result when item changes
  useEffect(() => {
    setSelectedScoreResult(null);
  }, [selectedItem]);
  
  // Enhanced scroll-to-item function for deep-linking with retry logic
  const scrollToSelectedItem = useCallback((itemId: string, maxRetries = 10, retryDelay = 100) => {
    let attempts = 0;
    
    const attemptScroll = () => {
      attempts++;
      const itemElement = itemRefsMap.current.get(itemId);
      
      if (itemElement) {
        // Calculate the position with 12px padding (Tailwind 3)
        const elementRect = itemElement.getBoundingClientRect();
        const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const targetScrollTop = currentScrollTop + elementRect.top - 12; // 12px padding
        
        window.scrollTo({
          top: targetScrollTop,
          behavior: 'smooth'
        });
        
        return true; // Success
      } else if (attempts < maxRetries) {
        setTimeout(attemptScroll, retryDelay);
        return false; // Retry needed
      } else {
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
            itemId: string;
            name: string;
          }>;
        };
      }>(`
        query ListIdentifierByValue($value: String!) {
          listIdentifierByValue(value: $value) {
            items {
              itemId
              name
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
        const itemId = identifier.itemId;
        if (itemId) {
          // Navigate to the item without remount
          window.history.pushState({}, '', `/lab/items/${itemId}`)
          setSelectedItem(itemId)
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
  }, []);

  // Handle search form submission
  const handleSearchSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(searchValue);
  }, [handleSearch, searchValue]);
  
  // Function to fetch a specific item by ID
  const fetchSpecificItem = useCallback(async (itemId: string) => {
    if (!selectedAccount) {
      return null;
    }
    
    // Check one more time if the item is now available before fetching
    if (items.some(item => item.id === itemId)) {
      return items.find(item => item.id === itemId) || null;
    }
    
    setSpecificItemLoading(true);
    
    // Add a timeout to prevent hanging forever
    const timeoutId = setTimeout(() => {
      setSpecificItemLoading(false);
      setFailedItemFetches(prev => new Set(prev).add(itemId));
    }, 30000); // 30 second timeout
    
    try {
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
          metadata?: string;
          attachedFiles?: string[];
          text?: string;
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
            metadata
            attachedFiles
            text
            itemIdentifiers {
              items {
                itemId
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
      
      if (response.data?.getItem) {
        const item = response.data.getItem;
        
        // Transform the item to match our expected format
        const transformedItem = transformItem(item, { isNew: false });
        
        // Add the item to the beginning of the list if it's not already there
        setItems(prevItems => {
          const exists = prevItems.some(existingItem => existingItem.id === item.id);
          if (!exists) {
            return [transformedItem, ...prevItems];
          }
          return prevItems;
        });
        
        // Track that this item was specifically fetched (not naturally in first page)
        setSpecificallyFetchedItems(prev => new Set(prev).add(item.id));
        
        return transformedItem;
      }
      
      // Item not found, mark as failed
      setFailedItemFetches(prev => new Set(prev).add(itemId));
      return null;
    } catch (error) {
      console.error('Error fetching specific item:', error);
      // Mark as failed on error too
      setFailedItemFetches(prev => new Set(prev).add(itemId));
      return null;
    } finally {
      clearTimeout(timeoutId);
      setSpecificItemLoading(false);
    }
  }, [selectedAccount, items]); // Include items to check if item is now available
  
  // Clear failed fetches and specifically fetched items when account changes
  useEffect(() => {
    if (selectedAccount) {
      setFailedItemFetches(new Set());
      setSpecificallyFetchedItems(new Set());
      // Clear score results refetch ref when account changes
      scoreResultsRefetchRef.current = null;
      // Reset hasInitiallyLoaded when account changes
      setHasInitiallyLoaded(false);
    }
  }, [selectedAccount?.id]);
  
  // Clear score results refetch ref when selected item changes
  useEffect(() => {
    return () => {
      scoreResultsRefetchRef.current = null;
    };
  }, [selectedItem]);

  // Silent refresh function for wake-from-sleep scenarios
  const silentRefresh = useCallback(async () => {
    if (!selectedAccount) return;
    
    try {
      // Use the same logic as throttledRefetch but ensure it's truly silent
      const accountId = selectedAccount.id;
      let itemsFromDirectQuery: any[] = [];
      
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
                metadata
                attachedFiles
                text
                itemIdentifiers {
                  items {
                    itemId
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
          listScoreResultByScorecardIdAndUpdatedAt: {
            items: Array<{
              itemId: string;
              item: any;
            }>;
            nextToken: string | null;
          }
        }>(`
          query SilentRefreshItemsByScorecardViaScoreResults($scorecardId: String!, $limit: Int!) {
            listScoreResultByScorecardIdAndUpdatedAt(
              scorecardId: $scorecardId,
              sortDirection: DESC,
              limit: $limit
            ) {
              items {
                itemId
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
                  metadata
                  attachedFiles
                  text
                  itemIdentifiers {
                    items {
                      itemId
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
        
        if (directQuery.data?.listScoreResultByScorecardIdAndUpdatedAt?.items) {
          // Get unique items from score results
          const itemsMap = new Map();
          directQuery.data.listScoreResultByScorecardIdAndUpdatedAt.items.forEach(result => {
            if (result.item && !itemsMap.has(result.item.id)) {
              itemsMap.set(result.item.id, result.item);
            }
          });
          
          itemsFromDirectQuery = Array.from(itemsMap.values()).sort((a, b) => {
            const dateA = new Date(a.createdAt || '').getTime();
            const dateB = new Date(b.createdAt || '').getTime();
            return dateB - dateA;
          });
        } else {
          itemsFromDirectQuery = [];
        }
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
                metadata
                attachedFiles
                text
                itemIdentifiers {
                  items {
                    itemId
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
            return { ...newItem, isNew: true }; // Mark new items as new!
          });
        
        // Update existing items and add new ones at the beginning
        const updatedItems = prevItems.map(prevItem => {
          const freshItem = transformedItems.find(item => item.id === prevItem.id);
          if (freshItem) {
            return {
              // Start with existing item to preserve metadata and other fields
              ...prevItem,
              // Only update fields that are present in the fresh data
              ...(freshItem.externalId !== undefined && { externalId: freshItem.externalId }),
              ...(freshItem.description !== undefined && { description: freshItem.description }),
              ...(freshItem.updatedAt !== undefined && { updatedAt: freshItem.updatedAt }),
              ...(freshItem.identifiers !== undefined && { identifiers: freshItem.identifiers }),
              ...(freshItem.metadata !== undefined && { metadata: freshItem.metadata }),
              ...(freshItem.attachedFiles !== undefined && { attachedFiles: freshItem.attachedFiles }),
              ...(freshItem.text !== undefined && { text: freshItem.text }),
              // Preserve isNew status
              isNew: prevItem.isNew,
            };
          }
          return prevItem;
        });
        
        // Add timeout to clear isNew flag for the new items found in silent refresh
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
      
      // Also refresh score result counts silently
      if (scoreCountManagerRef.current) {
        scoreCountManagerRef.current.refreshAllCounts();
      }
      
      // Refresh score results for selected item if applicable
      if (scoreResultsRefetchRef.current) {
        scoreResultsRefetchRef.current();
      }
      
    } catch (error) {
      console.error('Error during silent refresh:', error);
    }
  }, [selectedAccount, selectedScorecard, selectedScore, isErrorFilterActive]);

  // Enhanced throttled refresh that handles selected item immediately
  const throttledRefreshScoreCounts = useCallback((priorityItemId?: string) => {
    // If there's a priority item (like the selected item), refresh it immediately
    if (priorityItemId && scoreCountManagerRef.current) {
      scoreCountManagerRef.current.refreshItemCount(priorityItemId);
    }
    
    // Still throttle the bulk refresh for all other items
    if (scoreCountRefetchTimeoutRef.current) {
      clearTimeout(scoreCountRefetchTimeoutRef.current);
    }
  
    scoreCountRefetchTimeoutRef.current = setTimeout(() => {
      if (scoreCountManagerRef.current) {
        scoreCountManagerRef.current.refreshAllCounts();
      }
    }, 2000); // 2-second debounce for bulk updates
  }, []);

  // Helper function to check if an item should be shown based on current filters
  const shouldShowItemInCurrentFilter = useCallback(async (item: any): Promise<boolean> => {
    // If no error filter is active, show all items
    if (!isErrorFilterActive) {
      return true;
    }
    
    // If error filter is active, check if this item has error ScoreResults
    try {
      const errorScoreResultsQuery = await graphqlRequest<{
        listScoreResultByItemIdAndUpdatedAt: {
          items: Array<{
            id: string;
            value?: string;
            explanation?: string;
          }>;
        }
      }>(`
        query CheckItemForErrors($itemId: String!) {
          listScoreResultByItemIdAndUpdatedAt(
            itemId: $itemId,
            sortDirection: DESC,
            limit: 50
          ) {
            items {
              id
              value
              explanation
            }
          }
        }
      `, {
        itemId: item.id
      });
      
      if (errorScoreResultsQuery.data?.listScoreResultByItemIdAndUpdatedAt?.items) {
        // Check if any of this item's ScoreResults have errors
        const hasErrors = errorScoreResultsQuery.data.listScoreResultByItemIdAndUpdatedAt.items.some(result => {
          const value = result.value?.toLowerCase() || '';
          const explanation = result.explanation?.toLowerCase() || '';
          
          return value.includes('error') || 
                 value.includes('fail') || 
                 value.includes('exception') || 
                 explanation.includes('error') || 
                 explanation.includes('fail') || 
                 explanation.includes('exception') ||
                 explanation.includes('timeout') ||
                 explanation.includes('not found') ||
                 explanation.includes('invalid');
        });
        
        return hasErrors;
      }
      
      return false; // No ScoreResults found, so no errors
    } catch (error) {
      console.error('Error checking if item should be shown:', error);
      return false; // On error, don't show the item when error filter is active
    }
  }, [isErrorFilterActive]);

  // Restart subscriptions function
  const restartSubscriptions = useCallback(() => {
    if (!selectedAccount || isLoadingAccounts) return;
    
    // Clean up existing subscriptions
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
    
    // Restart subscriptions with a small delay to ensure cleanup completed
    setTimeout(() => {
      // Item creation subscription
      const createSubscription = observeItemCreations().subscribe({
        next: async ({ data: newItem }) => {
          if (!newItem) {
            return;
          }
          
          if (newItem.accountId === selectedAccount.id) {
            try {
              // Check if this item should be shown based on current filters
              const shouldShow = await shouldShowItemInCurrentFilter(newItem);
              
              if (shouldShow) {
                const transformedNewItem = transformItem(newItem, { isNew: true });
                setItems(prevItems => [transformedNewItem, ...prevItems]);
                
                toast.success('🎉 New item detected! Refreshing...', {
                  duration: 3000,
                });
                
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
            } catch (error) {
              console.error('Error checking if new item should be shown in restart subscription:', error);
              // On error during filter check, don't add the item to avoid showing unfiltered content
            }
          }
        },
        error: (error) => {
          console.error('Item creation subscription error:', error);
          toast.error("Error in item subscription.");
        }
      });
      
      // Item update subscription
             const updateSubscription = observeItemUpdates().subscribe({
         next: async ({ data: updatedItem, needsRefetch }) => {
           if (needsRefetch && !updatedItem) {
             silentRefresh();
             return;
           }
          
          if (!updatedItem) {
            return;
          }
          
          if (updatedItem.accountId === selectedAccount.id) {
            try {
              // Check if this item should be shown based on current filters
              const shouldShow = await shouldShowItemInCurrentFilter(updatedItem);
              
              setItems(prevItems => {
                const existingItemIndex = prevItems.findIndex(item => item.id === updatedItem.id);
                const itemExists = existingItemIndex !== -1;
                
                if (shouldShow) {
                  if (itemExists) {
                    // Update existing item
                    const updatedItems = [...prevItems];
                    updatedItems[existingItemIndex] = {
                      // Start with the existing item to preserve all existing data
                      ...prevItems[existingItemIndex],
                      // Only update fields that are actually present in the subscription data
                      ...(updatedItem.externalId !== undefined && { externalId: updatedItem.externalId }),
                      ...(updatedItem.description !== undefined && { description: updatedItem.description }),
                      ...(updatedItem.updatedAt !== undefined && { updatedAt: updatedItem.updatedAt }),
                      ...(updatedItem.identifiers !== undefined && { identifiers: transformIdentifiers(updatedItem) }),
                      // Only update metadata if it's actually present in the update
                      ...(updatedItem.metadata !== undefined && { 
                        metadata: typeof updatedItem.metadata === 'string' ? JSON.parse(updatedItem.metadata) : updatedItem.metadata 
                      }),
                      // Only update attachedFiles if it's actually present in the update  
                      ...(updatedItem.attachedFiles !== undefined && { attachedFiles: updatedItem.attachedFiles }),
                      // Only update text if it's actually present in the update
                      ...(updatedItem.text !== undefined && { text: updatedItem.text }),
                    };
                    return updatedItems;
                  } else {
                    // CRITICAL FIX: Only add items that weren't previously visible if we're NOT in error filter mode
                    // This prevents existing items from suddenly appearing when they get new score results
                    if (!isErrorFilterActive) {
                      // Not in error filter mode - safe to add items that now match other filters
                      const transformedItem = transformItem(updatedItem, { isNew: false });
                      return [transformedItem, ...prevItems];
                    } else {
                      // In error filter mode - don't add existing items that just got score results
                      // Only new items (handled by item creation subscription) should appear
                      return prevItems;
                    }
                  }
                } else {
                  if (itemExists) {
                    // Remove item that should no longer be shown
                    return prevItems.filter(item => item.id !== updatedItem.id);
                  } else {
                    // Item doesn't exist and shouldn't be shown - no change
                    return prevItems;
                  }
                }
              });
            } catch (error) {
              console.error('Error checking if updated item should be shown in restart subscription:', error);
              // On error during filter check, don't modify the items list to avoid inconsistent state
            }
            
            if (scoreCountManagerRef.current) {
              scoreCountManagerRef.current.clearCount(updatedItem.id);
              scoreCountManagerRef.current.loadCountForItem(updatedItem.id);
            }
          }
        },
        error: (error) => {
          console.error('Item update subscription error:', error);
          toast.error("Error in item update subscription.");
        }
      });
      
      // Score result subscription
      const scoreResultSubscription = observeScoreResultChanges().subscribe({
        next: async ({ data: changeEvent }) => {
          if (!changeEvent) {
            return;
          }
          
          try {
            if (scoreCountManagerRef.current) {
              // Immediately refresh the selected item, throttle everything else
              throttledRefreshScoreCounts(selectedItem || undefined);
            }
            
            if (scoreResultsRefetchRef.current) {
              scoreResultsRefetchRef.current();
            }
          } catch (error) {
            console.error('Error handling score result change:', error);
          }
        },
        error: (error) => {
          console.error('Score result subscription error:', error);
          toast.error("Error in score result subscription.");
        }
      });
      
      itemSubscriptionRef.current = createSubscription;
      itemUpdateSubscriptionRef.current = updateSubscription;
      scoreResultSubscriptionRef.current = scoreResultSubscription;
    }, 100);
  }, [selectedAccount, isLoadingAccounts, silentRefresh, throttledRefreshScoreCounts, selectedItem, shouldShowItemInCurrentFilter]);

  // Page Visibility API - detect wake from sleep
  useEffect(() => {
    const handleVisibilityChange = () => {
      const isVisible = !document.hidden;
      const now = Date.now();
      
      if (isVisible && !isPageVisibleRef.current) {
        // Page became visible
        isPageVisibleRef.current = true;
        
        if (pageHiddenTimeRef.current && (now - pageHiddenTimeRef.current) > WAKE_THRESHOLD_MS) {
          // Page was hidden for more than the threshold - likely wake from sleep
          console.log('Wake from sleep detected, performing silent refresh...');
          
          // Perform silent refresh and restart subscriptions
          silentRefresh();
          restartSubscriptions();
        }
        
        pageHiddenTimeRef.current = null;
      } else if (!isVisible && isPageVisibleRef.current) {
        // Page became hidden
        isPageVisibleRef.current = false;
        pageHiddenTimeRef.current = now;
      }
    };
    
    // Set initial state
    isPageVisibleRef.current = !document.hidden;
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [silentRefresh, restartSubscriptions]);
  
  // Track the previous item ID to only scroll when it actually changes
  const prevItemIdRef = useRef<string | null>(null);
  
  // Handle browser back/forward navigation
  useEffect(() => {
    const handlePopState = () => {
      const pathMatch = window.location.pathname.match(/\/lab\/items\/(.+)/)
      const itemIdFromUrl = pathMatch ? pathMatch[1] : null
      
      if (itemIdFromUrl !== selectedItem) {
        setSelectedItem(itemIdFromUrl)
        if (!itemIdFromUrl) {
          setIsFullWidth(false)
          prevItemIdRef.current = null
        }
      }
    }
    
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [selectedItem])
  
  // Initial sync from URL params (only on mount or when navigating to this page)
  useEffect(() => {
    // Handle both route structures: /lab/items and /lab/items/[id]
    const itemId = params.id as string
    
    if (itemId && itemId !== selectedItem) {
      setSelectedItem(itemId)
    } else if (!itemId && selectedItem) {
      // If we're on /lab/items but still have a selectedItem, clear it
      setSelectedItem(null)
      setIsFullWidth(false)
    }
  }, [params.id]) // Only depend on params.id, not selectedItem

  // Handle deep-linking view logic after items are loaded (primarily for URL navigation)
  useEffect(() => {
    if (selectedItem && !isLoadingAccounts && selectedAccount) {
      // Wait for initial items to be loaded before making decisions
      if (items.length === 0 && isLoading) {
        return;
      }
      
      const itemInFirstPage = items.some(item => item.id === selectedItem);
      const wasSpecificallyFetched = specificallyFetchedItems.has(selectedItem);
      
      if (itemInFirstPage) {
        // Item is in the loaded items
        if (!wasSpecificallyFetched) {
          // Item is naturally in first page
          // Only set view mode if it hasn't been set by handleItemClick
          // (Check if prevItemIdRef is already set, which indicates handleItemClick handled it)
          if (prevItemIdRef.current !== selectedItem) {
            if (!isNarrowViewport) {
              setIsFullWidth(false);
            }
            
            // Scroll to the item
            prevItemIdRef.current = selectedItem;
            setTimeout(() => {
              scrollToSelectedItem(selectedItem);
            }, 50);
          }
        }
        // If it was specifically fetched, keep the current view mode (likely full-width)
      } else if (items.length > 0 && !isLoading && !specificItemLoading) {
        // Item is not in first page and first page has been loaded - fetch it specifically
        // Added check for specificItemLoading to prevent multiple concurrent fetches
        if (!isNarrowViewport) {
          setIsFullWidth(true); // Show full-width for specifically fetched items
        }
        
        // Only fetch if we haven't already tried and we're not currently loading
        if (!wasSpecificallyFetched && !failedItemFetches.has(selectedItem)) {
          fetchSpecificItem(selectedItem);
          prevItemIdRef.current = selectedItem;
        }
      }
    }
  }, [selectedItem, items.length, isLoading, isLoadingAccounts, selectedAccount, isNarrowViewport, scrollToSelectedItem, specificallyFetchedItems, failedItemFetches, fetchSpecificItem, specificItemLoading]);

  
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
        // Determine if we should filter by scorecard, score, account, or errors
        const useScorecard = selectedScorecard !== null && selectedScorecard !== undefined;
        const useScore = selectedScore !== null && selectedScore !== undefined;
        
        if (isErrorFilterActive) {
          // Filter by items that have error ScoreResults - load more (client-side filtering)
          const errorScoreResultsQuery = await graphqlRequest<{
            listScoreResultByAccountIdAndUpdatedAt: {
              items: Array<{
                itemId: string;
                item: any;
                value?: string;
                explanation?: string;
              }>;
              nextToken: string | null;
            }
          }>(`
            query ListMoreErrorScoreResults($accountId: String!, $limit: Int!, $nextToken: String) {
              listScoreResultByAccountIdAndUpdatedAt(
                accountId: $accountId,
                sortDirection: DESC,
                limit: $limit,
                nextToken: $nextToken
              ) {
                items {
                  itemId
                  value
                  explanation
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
                    metadata
                    attachedFiles
                    text
                    itemIdentifiers {
                      items {
                        itemId
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
            accountId: selectedAccount.id,
            limit: 1000,
            nextToken: nextToken
          });
          
          console.debug('- LoadMore Error query response:', errorScoreResultsQuery);
          console.debug('- LoadMore Raw error ScoreResults found:', errorScoreResultsQuery.data?.listScoreResultByAccountIdAndUpdatedAt?.items?.length || 0);
          
          if (errorScoreResultsQuery.data?.listScoreResultByAccountIdAndUpdatedAt?.items) {
            // Filter for ScoreResults that indicate errors (client-side filtering)
            const errorScoreResults = errorScoreResultsQuery.data.listScoreResultByAccountIdAndUpdatedAt.items.filter(result => {
              // Look for error indicators in the value or explanation
              const value = result.value?.toLowerCase() || '';
              const explanation = result.explanation?.toLowerCase() || '';
              
              // Check for common error patterns
              return value.includes('error') || 
                     value.includes('fail') || 
                     value.includes('exception') || 
                     explanation.includes('error') || 
                     explanation.includes('fail') || 
                     explanation.includes('exception') ||
                     explanation.includes('timeout') ||
                     explanation.includes('not found') ||
                     explanation.includes('invalid');
            });
            
            console.debug('- LoadMore Filtered error ScoreResults:', errorScoreResults.length);
            
            // Get unique items from error score results
            const itemsMap = new Map();
            errorScoreResults.forEach(result => {
              if (result.item && !itemsMap.has(result.item.id)) {
                itemsMap.set(result.item.id, result.item);
              }
            });
            
            console.debug('- LoadMore Items map size after deduplication:', itemsMap.size);
            
            itemsFromDirectQuery = Array.from(itemsMap.values()).sort((a, b) => {
              const dateA = new Date(a.createdAt || '').getTime();
              const dateB = new Date(b.createdAt || '').getTime();
              return dateB - dateA;
            });
            nextTokenFromDirectQuery = errorScoreResults.length >= 1000 ? errorScoreResultsQuery.data.listScoreResultByAccountIdAndUpdatedAt.nextToken : null;
            console.debug('- ✅ LoadMore Unique error items found:', itemsFromDirectQuery.length);
            
            // Update the set of items with errors (append to existing)
            const newErrorItemIds = new Set(Array.from(itemsMap.keys()));
            setItemsWithErrors(prev => new Set([...prev, ...newErrorItemIds]));
          } else {
            console.debug('- ❌ LoadMore No error ScoreResults found or invalid response structure');
          }
        } else if (useScore) {
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
                  metadata
                  attachedFiles
                  text
                  itemIdentifiers {
                    items {
                      itemId
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
          // If only a scorecard is selected, get items through ScoreResults
          const directQuery = await graphqlRequest<{
            listScoreResultByScorecardIdAndUpdatedAt: {
              items: Array<{
                itemId: string;
                item: any;
              }>;
              nextToken: string | null;
            }
          }>(`
            query LoadMoreItemsByScorecardViaScoreResults($scorecardId: String!, $limit: Int!, $nextToken: String) {
              listScoreResultByScorecardIdAndUpdatedAt(
                scorecardId: $scorecardId,
                sortDirection: DESC,
                limit: $limit,
                nextToken: $nextToken
              ) {
                items {
                  itemId
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
                    metadata
                    attachedFiles
                    text
                    itemIdentifiers {
                      items {
                        itemId
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
          
          if (directQuery.data?.listScoreResultByScorecardIdAndUpdatedAt?.items) {
            // Get unique items from score results
            const itemsMap = new Map();
            directQuery.data.listScoreResultByScorecardIdAndUpdatedAt.items.forEach(result => {
              if (result.item && !itemsMap.has(result.item.id)) {
                itemsMap.set(result.item.id, result.item);
              }
            });
            
            itemsFromDirectQuery = Array.from(itemsMap.values()).sort((a, b) => {
              const dateA = new Date(a.createdAt || '').getTime();
              const dateB = new Date(b.createdAt || '').getTime();
              return dateB - dateA;
            });
            nextTokenFromDirectQuery = directQuery.data.listScoreResultByScorecardIdAndUpdatedAt.nextToken;
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
                  metadata
                  attachedFiles
                  text
                  itemIdentifiers {
                    items {
                      itemId
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
  }, [isLoadingMore, nextToken, selectedAccount, selectedScorecard, selectedScore, isErrorFilterActive, setItems, setNextToken, setIsLoadingMore]);

  // Fetch items from the API
  const fetchItems = useCallback(async () => {
    if (!user) {
      return;
    }
    
    if (!selectedAccount) {
      return;
    }
    
    setIsLoading(true);
    
    try {
      // Use the account ID from the context
      const accountId = selectedAccount.id;
      
      // Skip the amplifyClient.Item.list() call and only use the direct GraphQL query approach
      let itemsFromDirectQuery: any[] = [];
      let nextTokenFromDirectQuery: string | null = null;
      
      try {
        // Determine if we should filter by scorecard, score, account, or errors
        const useScorecard = selectedScorecard !== null && selectedScorecard !== undefined;
        const useScore = selectedScore !== null && selectedScore !== undefined;
        
        if (isErrorFilterActive) {
          // Filter by items that have error ScoreResults using the same GSI as error counting
          console.debug('🔍 FILTERING BY ERROR SCORE RESULTS (using GSI)');
          console.debug('- Account ID:', accountId);
          
          // Use the same GSI as the error counting to maintain consistency
          const errorScoreResultsQuery = await graphqlRequest<{
            listScoreResultByAccountIdAndCodeAndUpdatedAt: {
              items: Array<{
                id: string;
                itemId: string;
                updatedAt: string;
                code?: string;
                value?: string;
                explanation?: string;
                item: any;
              }>;
              nextToken: string | null;
            }
          }>(`
            query ListErrorScoreResultsGSI($accountId: String!, $limit: Int!) {
              listScoreResultByAccountIdAndCodeAndUpdatedAt(
                accountId: $accountId,
                codeUpdatedAt: { beginsWith: { code: "5" } },
                sortDirection: DESC,
                limit: $limit
              ) {
                items {
                  id
                  itemId
                  updatedAt
                  code
                  value
                  explanation
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
                    metadata
                    attachedFiles
                    text
                    itemIdentifiers {
                      items {
                        itemId
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
            accountId: accountId,
            limit: 1000
          });
          
          console.debug('- GSI Error query response:', errorScoreResultsQuery);
          console.debug('- Raw error ScoreResults found from GSI:', errorScoreResultsQuery.data?.listScoreResultByAccountIdAndCodeAndUpdatedAt?.items?.length || 0);
          
          if (errorScoreResultsQuery.data?.listScoreResultByAccountIdAndCodeAndUpdatedAt?.items) {
            const errorScoreResults = errorScoreResultsQuery.data.listScoreResultByAccountIdAndCodeAndUpdatedAt.items;
            
            console.debug('- GSI returned error ScoreResults:', errorScoreResults.length);
            
            // Get unique items from error score results
            const itemsMap = new Map();
            errorScoreResults.forEach((result, index) => {
              if (result.item && !itemsMap.has(result.item.id)) {
                itemsMap.set(result.item.id, result.item);
              } else if (!result.item) {
                console.debug(`- Warning: ScoreResult ${index} has no item data:`, {
                  itemId: result.itemId,
                  value: result.value,
                  explanation: result.explanation?.substring(0, 50) + '...'
                });
              }
            });
            
            console.debug('- Items map size after deduplication:', itemsMap.size);
            console.debug('- Sample item IDs from map:', Array.from(itemsMap.keys()).slice(0, 5));
            
            itemsFromDirectQuery = Array.from(itemsMap.values()).sort((a, b) => {
              const dateA = new Date(a.createdAt || '').getTime();
              const dateB = new Date(b.createdAt || '').getTime();
              return dateB - dateA;
            });
            nextTokenFromDirectQuery = errorScoreResults.length >= 1000 ? errorScoreResultsQuery.data.listScoreResultByAccountIdAndCodeAndUpdatedAt.nextToken : null;
            console.debug('- ✅ Unique error items found:', itemsFromDirectQuery.length);
            console.debug('- Sample error items (first 3):', itemsFromDirectQuery.slice(0, 3).map(item => ({ id: item.id, externalId: item.externalId })));
            
            // Update the set of items with errors
            const errorItemIds = new Set(Array.from(itemsMap.keys()));
            setItemsWithErrors(errorItemIds);
          } else {
            console.debug('- ❌ No error ScoreResults found or invalid response structure');
          }
        } else if (useScore) {
          // If a score is selected, filter by scoreId
          console.debug('Filtering by scoreId:', selectedScore);
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
                  metadata
                  attachedFiles
                  text
                  itemIdentifiers {
                    items {
                      itemId
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
          }
        } else if (useScorecard) {
          // If only a scorecard is selected, use optimized ScoreResult GSI
          console.log('🔍 SCORECARD FILTERING DEBUG (OPTIMIZED GSI):');
          console.log('- Selected scorecard ID:', selectedScorecard);
          console.log('- Account ID:', accountId);
          
          try {
            // Try the new optimized GSI first - sorted by itemId, createdAt for efficient deduplication
            const directQuery = await graphqlRequest<{
              listScoreResultByScorecardIdAndItemIdAndCreatedAt: {
                items: Array<{
                  itemId: string;
                  item: any;
                  createdAt: string;
                }>;
                nextToken: string | null;
              }
            }>(`
              query GetItemsByScorecardOptimized($scorecardId: String!, $limit: Int!) {
                listScoreResultByScorecardIdAndItemIdAndCreatedAt(
                  scorecardId: $scorecardId,
                  sortDirection: DESC,
                  limit: $limit
                ) {
                  items {
                    itemId
                    createdAt
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
                      metadata
                      attachedFiles
                      text
                      itemIdentifiers {
                        items {
                          itemId
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
              limit: 300  // Query more since we'll deduplicate
            });
            
            console.log('- OPTIMIZED GSI query response:', directQuery);
            console.log('- Raw ScoreResults count:', directQuery.data?.listScoreResultByScorecardIdAndItemIdAndCreatedAt?.items?.length || 0);
            
            if (directQuery.data?.listScoreResultByScorecardIdAndItemIdAndCreatedAt?.items) {
              // Efficiently deduplicate - since results are sorted by itemId, createdAt,
              // we can take the first (most recent) result for each itemId
              const itemsMap = new Map();
              let uniqueItemCount = 0;
              
              directQuery.data.listScoreResultByScorecardIdAndItemIdAndCreatedAt.items.forEach(result => {
                if (result.item && !itemsMap.has(result.item.id)) {
                  itemsMap.set(result.item.id, result.item);
                  uniqueItemCount++;
                  // Stop at 100 unique items for this page
                  if (uniqueItemCount >= 100) return;
                }
              });
              
              itemsFromDirectQuery = Array.from(itemsMap.values()).sort((a, b) => {
                const dateA = new Date(a.createdAt || '').getTime();
                const dateB = new Date(b.createdAt || '').getTime();
                return dateB - dateA;
              });
              
              nextTokenFromDirectQuery = directQuery.data.listScoreResultByScorecardIdAndItemIdAndCreatedAt.nextToken;
              console.log('- ✅ Using optimized GSI! Unique items:', itemsFromDirectQuery.length);
            } else {
              console.log('- Optimized GSI not available yet, using current method');
              throw new Error('Optimized GSI not ready, use current method');
            }
            
          } catch (error) {
            console.log('- Optimized GSI error:', error);
            console.log('- Using current ScoreResult method');
            
            // Current ScoreResult-based approach
            const currentQuery = await graphqlRequest<{
              listScoreResultByScorecardIdAndUpdatedAt: {
                items: Array<{
                  itemId: string;
                  item: any;
                }>;
                nextToken: string | null;
              }
            }>(`
              query GetItemsByScorecardViaScoreResults($scorecardId: String!, $limit: Int!) {
                listScoreResultByScorecardIdAndUpdatedAt(
                  scorecardId: $scorecardId,
                  sortDirection: DESC,
                  limit: $limit
                ) {
                  items {
                    itemId
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
                      metadata
                      attachedFiles
                      text
                      itemIdentifiers {
                        items {
                          itemId
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
            
            if (currentQuery.data?.listScoreResultByScorecardIdAndUpdatedAt?.items) {
              // Get unique items from score results
              const itemsMap = new Map();
              currentQuery.data.listScoreResultByScorecardIdAndUpdatedAt.items.forEach(result => {
                if (result.item && !itemsMap.has(result.item.id)) {
                  itemsMap.set(result.item.id, result.item);
                }
              });
              
              itemsFromDirectQuery = Array.from(itemsMap.values()).sort((a, b) => {
                const dateA = new Date(a.createdAt || '').getTime();
                const dateB = new Date(b.createdAt || '').getTime();
                return dateB - dateA;
              });
              nextTokenFromDirectQuery = currentQuery.data.listScoreResultByScorecardIdAndUpdatedAt.nextToken;
              console.log('- ⚠️ Using current ScoreResult method, items found:', itemsFromDirectQuery.length);
            }
          }
        } else {
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
                  metadata
                  attachedFiles
                  text
                  itemIdentifiers {
                    items {
                      itemId
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
          }
          
          // Clear items with errors when not filtering by errors
          setItemsWithErrors(new Set());
        }
      } catch (error) {
        console.error('Error in GraphQL query:', error);
      }
      
      const itemsToUse = itemsFromDirectQuery;
      const nextTokenToUse = nextTokenFromDirectQuery;
      
      const transformedItems = itemsToUse.map(item => transformItem(item, { isNew: false }));
      
      setItems(transformedItems);
      setNextToken(nextTokenToUse);
      setHasInitiallyLoaded(true);
      
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching items:', error);
      setIsLoading(false);
    }
  }, [user, selectedAccount, setIsLoading, setItems, setNextToken, selectedScorecard, selectedScore, isErrorFilterActive]);
  
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
                  metadata
                  attachedFiles
                  text
                  itemIdentifiers {
                    items {
                      itemId
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
            listScoreResultByScorecardIdAndUpdatedAt: {
              items: Array<{
                itemId: string;
                item: any;
              }>;
              nextToken: string | null;
            }
          }>(`
            query ThrottledRefreshItemsByScorecardViaScoreResults($scorecardId: String!, $limit: Int!) {
              listScoreResultByScorecardIdAndUpdatedAt(
                scorecardId: $scorecardId,
                sortDirection: DESC,
                limit: $limit
              ) {
                items {
                  itemId
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
                    metadata
                    attachedFiles
                    text
                    itemIdentifiers {
                      items {
                        itemId
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
          
          if (directQuery.data?.listScoreResultByScorecardIdAndUpdatedAt?.items) {
            // Get unique items from score results  
            const itemsMap = new Map();
            directQuery.data.listScoreResultByScorecardIdAndUpdatedAt.items.forEach(result => {
              if (result.item && !itemsMap.has(result.item.id)) {
                itemsMap.set(result.item.id, result.item);
              }
            });
            
            itemsFromDirectQuery = Array.from(itemsMap.values()).sort((a, b) => {
              const dateA = new Date(a.createdAt || '').getTime();
              const dateB = new Date(b.createdAt || '').getTime();
              return dateB - dateA;
            });
          } else {
            itemsFromDirectQuery = [];
          }
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
                  metadata
                  attachedFiles
                  text
                  itemIdentifiers {
                    items {
                      itemId
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
              return { ...newItem, isNew: true }; // Mark new items as new!
            });
          
          // Update existing items and add new ones at the beginning
          const updatedItems = prevItems.map(prevItem => {
            const freshItem = transformedItems.find(item => item.id === prevItem.id);
            if (freshItem) {
              return {
                // Start with existing item to preserve metadata and other fields
                ...prevItem,
                // Only update fields that are present in the fresh data
                ...(freshItem.externalId !== undefined && { externalId: freshItem.externalId }),
                ...(freshItem.description !== undefined && { description: freshItem.description }),
                ...(freshItem.updatedAt !== undefined && { updatedAt: freshItem.updatedAt }),
                ...(freshItem.identifiers !== undefined && { identifiers: freshItem.identifiers }),
                // Only update metadata if it's actually present in the fresh data
                ...(freshItem.metadata !== undefined && { metadata: freshItem.metadata }),
                // Only update attachedFiles if it's actually present in the fresh data
                ...(freshItem.attachedFiles !== undefined && { attachedFiles: freshItem.attachedFiles }),
                // Only update text if it's actually present in the fresh data
                ...(freshItem.text !== undefined && { text: freshItem.text }),
                // Preserve isNew status
                isNew: prevItem.isNew,
              };
            }
            return prevItem;
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
  }, [selectedAccount, selectedScorecard, selectedScore, isErrorFilterActive]);
  
  // Ref to track when we need to refetch items
  const shouldRefetchRef = useRef(false);
  
  // Mark when we need to refetch due to filter changes
  useEffect(() => {
    if (!isLoadingAccounts && selectedAccount) {
      shouldRefetchRef.current = true;
    }
  }, [selectedAccount?.id, isLoadingAccounts, selectedScorecard, selectedScore, isErrorFilterActive]);
  
  // Clear error filter when other filters change
  useEffect(() => {
    if (isErrorFilterActive && (selectedScorecard || selectedScore)) {
      setIsErrorFilterActive(false);
    }
  }, [selectedScorecard, selectedScore]);
  
  // Fetch items when the selected account or other filters change
  useEffect(() => {
    if (!isLoadingAccounts && selectedAccount && shouldRefetchRef.current) {
      shouldRefetchRef.current = false; // Reset the flag
      
      // Reset items and nextToken when filters change
      setItems([]);
      setNextToken(null);
      // Clear specifically fetched items since filter change redefines what "first page" means
      setSpecificallyFetchedItems(new Set());
      fetchItems();
    } else if (!isLoadingAccounts && !selectedAccount) {
      setItems([]); // Ensure items are cleared
      setNextToken(null);
      setIsLoading(false); // Stop loading indicator
    }
  }, [fetchItems, selectedAccount?.id, isLoadingAccounts]);

  // Initialize score count manager
  useEffect(() => {
    if (!scoreCountManagerRef.current) {
      scoreCountManagerRef.current = new ScoreResultCountManager();
      
      // Subscribe to count changes with better state management
      const unsubscribe = scoreCountManagerRef.current.subscribe((counts) => {
        // Simplified update - always accept the new counts
        // The ScoreResultCountManager already creates a new Map instance,
        // so React will detect the change properly
        setScoreResultCounts(counts);
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
    if (!selectedAccount || isLoadingAccounts) return; // Also wait for accounts to be loaded
    
    // Item creation subscription
    const createSubscription = observeItemCreations().subscribe({
      next: async ({ data: newItem }) => {
        if (!newItem) {
          return;
        }
        
        if (newItem.accountId === selectedAccount.id) {
          try {
            // Check if this item should be shown based on current filters
            const shouldShow = await shouldShowItemInCurrentFilter(newItem);
            
            if (shouldShow) {
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
          } catch (error) {
            console.error('Error checking if new item should be shown:', error);
            // On error during filter check, don't add the item to avoid showing unfiltered content
          }
        }
      },
      error: (error) => {
        console.error('Item creation subscription error:', error);
        toast.error("Error in item subscription.");
      }
    });
    
    // Item update subscription
    const updateSubscription = observeItemUpdates().subscribe({
      next: async ({ data: updatedItem, needsRefetch }) => {
        // Handle empty notifications that require a refetch
        if (needsRefetch && !updatedItem) {
          silentRefresh();
          return;
        }
        
        if (!updatedItem) {
          return;
        }
        
        if (updatedItem.accountId === selectedAccount.id) {
          try {
            // Check if this item should be shown based on current filters
            const shouldShow = await shouldShowItemInCurrentFilter(updatedItem);
            
            setItems(prevItems => {
              const existingItemIndex = prevItems.findIndex(item => item.id === updatedItem.id);
              const itemExists = existingItemIndex !== -1;
              
              if (shouldShow) {
                if (itemExists) {
                  // Update existing item
                  const updatedItems = [...prevItems];
                  updatedItems[existingItemIndex] = {
                    // Start with the existing item to preserve all existing data
                    ...prevItems[existingItemIndex],
                    // Only update fields that are actually present in the subscription data
                    ...(updatedItem.externalId !== undefined && { externalId: updatedItem.externalId }),
                    ...(updatedItem.description !== undefined && { description: updatedItem.description }),
                    ...(updatedItem.updatedAt !== undefined && { updatedAt: updatedItem.updatedAt }),
                    ...(updatedItem.identifiers !== undefined && { identifiers: transformIdentifiers(updatedItem) }),
                    // Only update metadata if it's actually present in the update
                    ...(updatedItem.metadata !== undefined && { 
                      metadata: typeof updatedItem.metadata === 'string' ? JSON.parse(updatedItem.metadata) : updatedItem.metadata 
                    }),
                    // Only update attachedFiles if it's actually present in the update  
                    ...(updatedItem.attachedFiles !== undefined && { attachedFiles: updatedItem.attachedFiles }),
                    // Only update text if it's actually present in the update
                    ...(updatedItem.text !== undefined && { text: updatedItem.text }),
                  };
                  return updatedItems;
                } else {
                  // CRITICAL FIX: Only add items that weren't previously visible if we're NOT in error filter mode
                  // This prevents existing items from suddenly appearing when they get new score results
                  if (!isErrorFilterActive) {
                    // Not in error filter mode - safe to add items that now match other filters
                    const transformedItem = transformItem(updatedItem, { isNew: false });
                    return [transformedItem, ...prevItems];
                  } else {
                    // In error filter mode - don't add existing items that just got score results
                    // Only new items (handled by item creation subscription) should appear
                    console.log('🚫 Preventing existing item from appearing in error filter due to score result update:', updatedItem.id);
                    return prevItems;
                  }
                }
              } else {
                if (itemExists) {
                  // Remove item that should no longer be shown
                  return prevItems.filter(item => item.id !== updatedItem.id);
                } else {
                  // Item doesn't exist and shouldn't be shown - no change
                  return prevItems;
                }
              }
            });
          } catch (error) {
            console.error('Error checking if updated item should be shown:', error);
            // On error during filter check, don't modify the items list to avoid inconsistent state
          }
          
          // Trigger a re-count of score results for this item
          if (scoreCountManagerRef.current) {
            scoreCountManagerRef.current.clearCount(updatedItem.id);
            scoreCountManagerRef.current.loadCountForItem(updatedItem.id);
          }
        }
      },
      error: (error) => {
        console.error('Item update subscription error:', error);
        toast.error("Error in item update subscription.");
      }
    });
    
    // Score result subscription
    const scoreResultSubscription = observeScoreResultChanges().subscribe({
      next: async ({ data: changeEvent }) => {
        if (!changeEvent) {
          return;
        }
        
        try {
          // Immediately refresh the selected item, throttle everything else
          if (scoreCountManagerRef.current) {
            throttledRefreshScoreCounts(selectedItem || undefined);
          }
          
          // Also refresh the detail view score results if there's a selected item
          if (scoreResultsRefetchRef.current) {
            scoreResultsRefetchRef.current();
          }
        } catch (error) {
          console.error('Error handling score result change:', error);
        }
      },
      error: (error) => {
        console.error('Score result subscription error:', error);
        toast.error("Error in score result subscription.");
      }
    });
    
    itemSubscriptionRef.current = createSubscription;
    itemUpdateSubscriptionRef.current = updateSubscription;
    scoreResultSubscriptionRef.current = scoreResultSubscription;
    
    return () => {
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
      if (scoreCountRefetchTimeoutRef.current) {
        clearTimeout(scoreCountRefetchTimeoutRef.current);
        scoreCountRefetchTimeoutRef.current = null;
      }
    };
  }, [selectedAccount, isLoadingAccounts, silentRefresh, throttledRefreshScoreCounts, selectedItem, shouldShowItemInCurrentFilter]); // Added selectedItem to ensure subscriptions capture current selection

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

    const filtered = items.filter(item => {
      // If no filters are applied, show all items
      if (!selectedScorecard && !selectedScore && filterConfig.length === 0) return true
      
      // Since we're now fetching items directly through ScoreResult filtering,
      // items already match the scorecard/score filter when they're retrieved.
      // We only need to apply additional filterConfig rules here.
      
      if (filterConfig.length === 0) {
        // No additional filters, so all fetched items should be shown
        return true;
      }
      
      // Apply additional filter config rules
      return filterConfig.some(group => {
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
    });
    
    return filtered;
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
    // Implement the logic for applying the sampling here
  }

  const handleTimeRangeChange = (range: string, customRange?: { from: Date | undefined; to: Date | undefined }) => {
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

  const renderSelectedItem = (naturalHeight = false) => {
    if (!selectedItem) {
      return null
    }

    // If accounts are still loading, show skeleton
    if (isLoadingAccounts) {
      return (
        <ItemCard
          variant="detail"
          item={{
            id: selectedItem,
            timestamp: new Date().toISOString(),
            scorecards: []
          } as ItemData}
          getBadgeVariant={getBadgeVariant}
          isFullWidth={isFullWidth}
          onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
          onClose={() => {
            setIsFullWidth(false);
            window.history.pushState({}, '', `/lab/items`)
            setSelectedItem(null)
          }}
          skeletonMode={true}
          readOnly={true}
          naturalHeight={naturalHeight}
        />
      )
    }

    const selectedItemData = items.find(item => item.id === selectedItem)
    
    const scoreCount = scoreResultCounts.get(selectedItem)
    const selectedItemWithCount = selectedItemData ? {
      ...selectedItemData,
      results: scoreCount?.count || selectedItemData.results,
      isLoadingResults: scoreCount?.isLoading || false,
      scorecardBreakdown: scoreCount?.scorecardBreakdown || undefined
    } : null
    
    // If item is not found, check if we should attempt to fetch it or if we're already loading
    if (!selectedItemWithCount) {
      // Only show skeleton if we're specifically loading this item or during initial load
      if (specificItemLoading || (!hasInitiallyLoaded && isLoading)) {
        return (
          <ItemCard
            variant="detail"
            item={{
              id: selectedItem,
              timestamp: new Date().toISOString(),
              scorecards: []
            } as ItemData}
            getBadgeVariant={getBadgeVariant}
            isFullWidth={isFullWidth}
            onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
            onClose={() => {
              setIsFullWidth(false);
              window.history.pushState({}, '', `/lab/items`)
              setSelectedItem(null)
            }}
            skeletonMode={true}
            readOnly={true}
            naturalHeight={naturalHeight}
          />
        )
      }
      
      // Only check failed fetches if we're not currently loading
      if (failedItemFetches.has(selectedItem)) {
        return (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-muted-foreground mb-2">Item not found</p>
              <p className="text-sm text-muted-foreground">
                The item with ID {selectedItem} could not be found.
              </p>
            </div>
          </div>
        )
      }
      
      // If we have a selected account and the item truly doesn't exist,
      // show an appropriate error message
      if (selectedAccount) {
        return (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-muted-foreground mb-2">Item not found</p>
              <p className="text-sm text-muted-foreground">
                The item with ID {selectedItem} could not be found.
              </p>
            </div>
          </div>
        )
      }
      
      // Only show not found if we have no account (shouldn't happen) 
      // or we've definitively determined the item doesn't exist
      return null
    }

    
    return (
      <ItemCard
        key={selectedItem} // Force re-render when selectedItem changes
        variant="detail"
        item={selectedItemWithCount as ItemData}
        getBadgeVariant={getBadgeVariant}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={() => {
          setIsFullWidth(false);
          // Use window.history to navigate back to grid view without remount
          window.history.pushState({}, '', `/lab/items`)
          setSelectedItem(null)
        }}
        onScoreResultsRefetchReady={(refetchFn) => {
          scoreResultsRefetchRef.current = refetchFn;
        }}
        onScoreResultSelect={handleScoreResultSelect}
        selectedScoreResultId={selectedScoreResult?.id}
        readOnly={true}
        naturalHeight={naturalHeight}
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

  const handleErrorClick = () => {
    // Clear other filters first
    setSelectedScorecard(null);
    setSelectedScore(null);
    setIsErrorFilterActive(true);
    // Clear other selections when switching to error mode
    setSelectedItem(null);
    setIsFullWidth(false);
    // Navigate to items list without specific item
    window.history.pushState({}, '', `/lab/items`);
  };

  const handleItemClick = (itemId: string) => {
    // Use window.history.pushState for truly shallow navigation that won't cause remount
    window.history.pushState({}, '', `/lab/items/${itemId}`)
    // Manually update the selected item state
    setSelectedItem(itemId)
    
    // Handle view mode for grid items (items in the first page)
    if (items.some(item => item.id === itemId)) {
      // Item is in first page - set up split view or full-width based on viewport
      if (isNarrowViewport) {
        setIsFullWidth(true)
      } else {
        setIsFullWidth(false)
        // Scroll to the selected item with retry logic - use a timeout to allow state to update first
        setTimeout(() => {
          scrollToSelectedItem(itemId);
          prevItemIdRef.current = itemId;
        }, 0);
      }
    } else {
      // Item is not in first page - let the useEffect handle fetching and view setup
      if (isNarrowViewport) {
        setIsFullWidth(true)
      } else {
        // For desktop, also set full-width for items not in first page
        setIsFullWidth(true)
      }
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

  // Show loading skeleton only for true initial load
  if (!hasInitiallyLoaded && isLoading) {
    return <ItemsDashboardSkeleton />
  }

  return (
    <div className="@container flex flex-col h-full p-3 overflow-hidden">
      {/* Fixed header - always show for wider viewports */}
      {!isNarrowViewport && (
        <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
          <div className="@[600px]:flex-grow w-full">
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
          
          {/* Error Filter Indicator */}
          {isErrorFilterActive && (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 px-2 py-1 bg-destructive text-foreground rounded-md text-sm">
                <AlertTriangle className="h-3 w-3" />
                <span>Errors</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsErrorFilterActive(false)}
                className="h-auto p-1 text-xs"
                title="Clear error filter"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          )}
          
          {/* Search Component */}
          <div className="flex items-center relative @[600px]:w-auto w-full">
            <form onSubmit={handleSearchSubmit} className="relative @[600px]:w-auto w-full">
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
                  className={`@[600px]:w-[200px] w-full h-9 pl-10 ${searchValue.trim() ? 'pr-20' : 'pr-3'} bg-card border-0 shadow-none focus:ring-0 focus:ring-offset-0 focus:outline-none focus:border-0 focus:shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:outline-none`}
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
      )}
      
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        {/* 
          Deep-linking rendering logic - all modes use consistent container structure
        */}

        {/* Content area - always uses the same base structure */}
        <div className="flex flex-1 min-h-0">
          {/* Left panel - grid content */}
          <div 
            className={`${selectedItem && !isNarrowViewport && (isFullWidth || selectedScoreResult) ? 'hidden' : 'flex-1'} h-full overflow-auto overflow-x-visible`}
            style={selectedItem && !isNarrowViewport && !isFullWidth && !selectedScoreResult ? {
              width: `${leftPanelWidth}%`
            } : undefined}
          >
            {/* Header for narrow viewports only */}
            {isNarrowViewport && (
              <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
                <div className="@[600px]:flex-grow w-full">
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
                
                {/* Error Filter Indicator */}
                {isErrorFilterActive && (
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 px-2 py-1 bg-destructive text-foreground rounded-md text-sm">
                      <AlertTriangle className="h-3 w-3" />
                      <span>Errors</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setIsErrorFilterActive(false)}
                      className="h-auto p-1 text-xs"
                      title="Clear error filter"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                )}
                
                {/* Search Component */}
                <div className="flex items-center relative @[600px]:w-auto w-full">
                  <form onSubmit={handleSearchSubmit} className="relative @[600px]:w-auto w-full">
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
                        className={`@[600px]:w-[200px] w-full h-9 pl-10 ${searchValue.trim() ? 'pr-20' : 'pr-3'} bg-card border-0 shadow-none focus:ring-0 focus:ring-offset-0 focus:outline-none focus:border-0 focus:shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 focus-visible:outline-none`}
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
            )}

            {/* Grid content or item content for mobile */}
            <div className="@container space-y-3 overflow-visible">
              {isNarrowViewport && selectedItem ? (
                // Mobile full-screen item view
                <div className="h-full">
                  {selectedScoreResult ? (
                    <ScoreResultCard
                      scoreResult={selectedScoreResult}
                      onClose={() => setSelectedScoreResult(null)}
                      naturalHeight={true}
                    />
                  ) : (
                    renderSelectedItem(true)
                  )}
                </div>
              ) : (
                // Grid view with gauges at top
                <>
                  {/* ItemsGauges at the top - only show when not in mobile selected item view */}
                  <ItemsGauges onErrorClick={handleErrorClick} />
                  
                  {isLoading ? (
                    <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 animate-pulse">
                      {[...Array(12)].map((_, i) => (
                        <ItemCardSkeleton key={i} />
                      ))}
                    </div>
                  ) : (
                    <GridContent
                      filteredItems={filteredItems}
                      selectedItem={selectedItem}
                      handleItemClick={handleItemClick}
                      getBadgeVariant={getBadgeVariant}
                      scoreCountManagerRef={scoreCountManagerRef}
                      itemRefsMap={itemRefsMap}
                      scoreResultCounts={scoreResultCounts}
                      nextToken={nextToken}
                      isLoadingMore={isLoadingMore}
                      loadMoreRef={loadMoreRef}
                      isLoading={isLoading}
                      hasInitiallyLoaded={hasInitiallyLoaded}
                      itemsWithErrors={itemsWithErrors}
                    />
                  )}
                </>
              )}
            </div>
          </div>

          {/* Divider for split view */}
          {selectedItem && !isNarrowViewport && !isFullWidth && !selectedScoreResult && (
            <div
              className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
              onMouseDown={handleDragStart}
            >
              <div className="absolute inset-0 rounded-full transition-colors duration-150 
                group-hover:bg-accent" />
            </div>
          )}

          {/* Right panel - item detail view */}
          {selectedItem && !isNarrowViewport && (
            <>
              {selectedScoreResult ? (
                // When score result is selected, show ItemCard and ScoreResultCard side by side, full-width
                <>
                  <div className="h-full overflow-hidden flex-1">
                    {renderSelectedItem()}
                  </div>
                  {/* Divider between ItemCard and ScoreResultCard */}
                  <div
                    className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
                  >
                    <div className="absolute inset-0 rounded-full transition-colors duration-150 \
                      group-hover:bg-accent" />
                  </div>
                  {/* Score result panel - takes equal space with ItemCard */}
                  <div className="h-full overflow-hidden flex-1">
                    <ScoreResultCard
                      scoreResult={selectedScoreResult}
                      onClose={() => setSelectedScoreResult(null)}
                      naturalHeight={false}
                    />
                  </div>
                </>
              ) : (
                // When no score result is selected, show normal item view
                <motion.div
                  key={selectedItem}
                  initial={{ x: '100%', opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  exit={{ x: '100%', opacity: 0 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  className="h-full overflow-hidden"
                  style={{ 
                    width: isFullWidth 
                      ? '100%' 
                      : `${100 - leftPanelWidth}%` 
                  }}
                >
                  {renderSelectedItem()}
                </motion.div>
              )}
            </>
          )}
        </div>
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


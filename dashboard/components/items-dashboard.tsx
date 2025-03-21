"use client"
import React, { useContext, useEffect, useMemo, useRef, useState, useCallback } from "react"
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
import { ScorecardContextProps } from "./ScorecardContext"
import { observeItemCreations } from '@/utils/subscriptions'
import { toast } from 'sonner'
import { useAccount } from '@/app/contexts/AccountContext'

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
  score?: string | number | null;
  date?: string;
  status?: string;
  results?: number;
  inferences?: number;
  cost?: string;
  isNew?: boolean; // Add this field to track new items
  
  // New field to store scoreResults grouped by scorecard
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
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [nextToken, setNextToken] = useState<string | null>(null);
  const { user } = useAuthenticator();
  // Use the account context instead of local state
  const { selectedAccount } = useAccount();
  const itemSubscriptionRef = useRef<{ unsubscribe: () => void } | null>(null);
  
  // Add a ref for the intersection observer
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  
  // Define handleLoadMore with useCallback to ensure it's stable across renders
  const handleLoadMore = useCallback(async () => {
    if (isLoadingMore || !nextToken) return;
    
    setIsLoadingMore(true);
    console.log('Loading more items with nextToken:', nextToken);
    
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
        
        console.log('Filter settings for load more:', {
          useScorecard,
          useScore,
          scorecardId: selectedScorecard,
          scoreId: selectedScore
        });
        
        if (useScore) {
          // If a score is selected, filter by scoreId
          console.log('Attempting direct GraphQL query for more items with scoreId:', selectedScore);
          const directQuery = await graphqlRequest<{ listItemByScoreIdAndUpdatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsMoreDirect($scoreId: String!, $limit: Int!, $nextToken: String) {
              listItemByScoreIdAndUpdatedAt(
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
                  scoreResults {
                    items {
                      id
                      value
                      explanation
                      confidence
                      scorecardId
                      scoreId
                      scorecard {
                        id
                        name
                      }
                      score {
                        id
                        name
                      }
                      updatedAt
                      createdAt
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
          
          console.log('Direct GraphQL query response for more items:', JSON.stringify(directQuery, null, 2));
          
          if (directQuery.data?.listItemByScoreIdAndUpdatedAt?.items) {
            console.log(`Found ${directQuery.data.listItemByScoreIdAndUpdatedAt.items.length} more items via direct GraphQL query`);
            // No need to sort as the GSI already returns items sorted by updatedAt
            itemsFromDirectQuery = directQuery.data.listItemByScoreIdAndUpdatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByScoreIdAndUpdatedAt.nextToken;
          } else {
            console.warn('No more items found in direct GraphQL query response');
          }
        } else if (useScorecard) {
          // If only a scorecard is selected, filter by scorecardId
          console.log('Attempting direct GraphQL query for more items with scorecardId:', selectedScorecard);
          const directQuery = await graphqlRequest<{ listItemByScorecardIdAndUpdatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsMoreDirect($scorecardId: String!, $limit: Int!, $nextToken: String) {
              listItemByScorecardIdAndUpdatedAt(
                scorecardId: $scorecardId, 
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
                  scoreResults {
                    items {
                      id
                      value
                      explanation
                      confidence
                      scorecardId
                      scoreId
                      scorecard {
                        id
                        name
                      }
                      score {
                        id
                        name
                      }
                      updatedAt
                      createdAt
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
          
          console.log('Direct GraphQL query response for more items:', JSON.stringify(directQuery, null, 2));
          
          if (directQuery.data?.listItemByScorecardIdAndUpdatedAt?.items) {
            console.log(`Found ${directQuery.data.listItemByScorecardIdAndUpdatedAt.items.length} more items via direct GraphQL query`);
            // No need to sort as the GSI already returns items sorted by updatedAt
            itemsFromDirectQuery = directQuery.data.listItemByScorecardIdAndUpdatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByScorecardIdAndUpdatedAt.nextToken;
          } else {
            console.warn('No more items found in direct GraphQL query response');
          }
        } else {
          // If neither scorecard nor score is selected, filter by accountId
          console.log('Attempting direct GraphQL query for more items with accountId:', selectedAccount.id);
          const directQuery = await graphqlRequest<{ listItemByAccountIdAndUpdatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsMoreDirect($accountId: String!, $limit: Int!, $nextToken: String) {
              listItemByAccountIdAndUpdatedAt(
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
                  scoreResults {
                    items {
                      id
                      value
                      explanation
                      confidence
                      scorecardId
                      scoreId
                      scorecard {
                        id
                        name
                      }
                      score {
                        id
                        name
                      }
                      updatedAt
                      createdAt
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
          
          console.log('Direct GraphQL query response for more items:', JSON.stringify(directQuery, null, 2));
          
          if (directQuery.data?.listItemByAccountIdAndUpdatedAt?.items) {
            console.log(`Found ${directQuery.data.listItemByAccountIdAndUpdatedAt.items.length} more items via direct GraphQL query`);
            // No need to sort as the GSI already returns items sorted by updatedAt
            itemsFromDirectQuery = directQuery.data.listItemByAccountIdAndUpdatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByAccountIdAndUpdatedAt.nextToken;
          } else {
            console.warn('No items found in direct GraphQL query response');
          }
        }
      } catch (error) {
        console.error('Error in direct GraphQL query for more items:', error);
      }
      
      // Use the items from the direct query
      const itemsToUse = itemsFromDirectQuery;
      const nextTokenToUse = nextTokenFromDirectQuery;
      
      // If no items are found, we'll log this information
      if (itemsToUse.length === 0) {
        console.log('No items found for this account. You may need to create some items first.');
      }
      
      // Transform the data to match the expected format
      const transformedItems = itemsToUse.map(item => {
        // Group scoreResults by scorecard
        const groupedScoreResults: GroupedScoreResults = {};
        
        console.log('Raw item before transformation:', {
          id: item.id,
          externalId: item.externalId,
          accountId: item.accountId,
          scorecardId: item.scorecardId,
          scoreId: item.scoreId,
          hasScoreResults: !!item.scoreResults,
          scoreResultsItemsCount: item.scoreResults?.items?.length,
          firstScoreResult: item.scoreResults?.items?.[0] 
        });
        
        if (item.scoreResults && item.scoreResults.items) {
          item.scoreResults.items.forEach((result: any) => {
            if (result.scorecardId) {
              // Create scorecard entry if it doesn't exist
              if (!groupedScoreResults[result.scorecardId]) {
                groupedScoreResults[result.scorecardId] = {
                  scorecardName: result.scorecard?.name || `Scorecard ${result.scorecardId.substring(0, 8)}`,
                  scores: []
                };
              }
              
              // Add score to the scorecard's scores if not already present
              const scoreExists = groupedScoreResults[result.scorecardId].scores.some(
                s => s.scoreId === result.scoreId
              );
              
              if (!scoreExists && result.scoreId) {
                groupedScoreResults[result.scorecardId].scores.push({
                  scoreId: result.scoreId,
                  scoreName: result.score?.name || `Score ${result.scoreId.substring(0, 8)}`
                });
              }
            }
          });
        } else if (item.scorecardId && !Object.keys(groupedScoreResults).length) {
          // If item has a scorecardId but no scoreResults, create a placeholder entry
          console.log('Item has scorecardId but no scoreResults:', item.scorecardId);
          
          // Try to add a placeholder entry using the scorecardId
          groupedScoreResults[item.scorecardId] = {
            scorecardName: `Scorecard ${item.scorecardId.substring(0, 8)}`,
            scores: []
          };
          
          // Add score if available
          if (item.scoreId) {
            groupedScoreResults[item.scorecardId].scores.push({
              scoreId: item.scoreId,
              scoreName: `Score ${item.scoreId.substring(0, 8)}`
            });
          }
        }
        
        console.log('Generated groupedScoreResults:', groupedScoreResults);
        
        // Get the primary scorecard and score name to display
        let primaryScorecardName = null;
        let primaryScoreName = null;
        
        // Logic to determine primary scorecard (first one with scores, or just first one)
        const scorecardIds = Object.keys(groupedScoreResults);
        if (scorecardIds.length > 0) {
          const firstScorecardWithScores = scorecardIds.find(
            id => groupedScoreResults[id].scores.length > 0
          ) || scorecardIds[0];
          
          primaryScorecardName = groupedScoreResults[firstScorecardWithScores].scorecardName;
          
          // Get first score if any exist
          if (groupedScoreResults[firstScorecardWithScores].scores.length > 0) {
            primaryScoreName = groupedScoreResults[firstScorecardWithScores].scores[0].scoreName;
          }
        }
        
        // Create the transformed item with all required fields
        const transformedItem = {
          id: item.id,
          accountId: item.accountId,
          externalId: item.externalId,
          description: item.description,
          evaluationId: item.evaluationId,
          updatedAt: item.updatedAt,
          createdAt: item.createdAt,
          isEvaluation: item.isEvaluation,
          // UI compatibility fields
          scorecard: primaryScorecardName,
          score: primaryScoreName, 
          date: item.updatedAt || item.createdAt,
          status: "Done", // Default status
          results: 0,
          inferences: 0,
          cost: "$0.000",
          isNew: true, // Mark all items as new for animation
          // Add grouped scoreResults
          groupedScoreResults: groupedScoreResults
        } as Item;
        
        console.log('Final transformed item:', {
          id: transformedItem.id,
          primaryScorecard: transformedItem.scorecard,
          primaryScore: transformedItem.score,
          groupedScoreResultsKeys: Object.keys(transformedItem.groupedScoreResults || {})
        });
        
        return transformedItem;
      });
      
      // Append the new items to the existing items
      setItems(prevItems => [...prevItems, ...transformedItems]);
      setNextToken(nextTokenToUse);
      
      // After a delay, remove the "isNew" flag with a staggered effect
      transformedItems.forEach((item, index) => {
        setTimeout(() => {
          setItems(prevItems => 
            prevItems.map(prevItem => 
              prevItem.id === item.id 
                ? { ...prevItem, isNew: false } 
                : prevItem
            )
          );
        }, 100 + (index * 100)); // Stagger the removal of the isNew flag
      });
    } catch (error) {
      console.error("Error fetching more items:", error);
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, nextToken, selectedAccount, selectedScorecard, selectedScore, setItems, setNextToken, setIsLoadingMore, graphqlRequest]);

  // Fetch items from the API
  const fetchItems = useCallback(async () => {
    if (!user) {
      console.log('User not authenticated, skipping item fetch');
      return;
    }
    
    if (!selectedAccount) {
      console.log('No account selected in context, skipping item fetch');
      return;
    }
    
    console.log('User authenticated, fetching items for account:', selectedAccount.id);
    setIsLoading(true);
    
    try {
      // Use the account ID from the context
      const accountId = selectedAccount.id;
      
      // Try using the Amplify client first
      try {
        const itemsResult = await amplifyClient.Item.list({
          filter: { accountId: { eq: accountId } },
          limit: 100,
          sort: { field: 'updatedAt', direction: 'DESC' },
          // Unfortunately, adding scoreResults here doesn't work well with Amplify Gen2
          // so we'll fall back to the direct GraphQL query
        });
        
        console.log(`Found ${itemsResult.data.length} items using Amplify client`);
        
        // Skip this approach to make this change complete
        if (false && itemsResult.data.length > 0) {
          // The Amplify client approach is disabled because we need scoreResults
        }
      } catch (error) {
        console.error("Error using Amplify client to fetch items:", error);
        // Continue with the direct GraphQL query approach
      }
      
      // Skip the amplifyClient.Item.list() call that's causing the error
      // and only use the direct GraphQL query approach
      let itemsFromDirectQuery: any[] = [];
      let nextTokenFromDirectQuery: string | null = null;
      
      try {
        // Determine if we should filter by scorecard, score, or account
        const useScorecard = selectedScorecard !== null && selectedScorecard !== undefined;
        const useScore = selectedScore !== null && selectedScore !== undefined;
        
        console.log('Filter settings:', {
          useScorecard,
          useScore,
          scorecardId: selectedScorecard,
          scoreId: selectedScore
        });
        
        if (useScore) {
          // If a score is selected, filter by scoreId
          console.log('Attempting direct GraphQL query for items with scoreId:', selectedScore);
          const directQuery = await graphqlRequest<{ listItemByScoreIdAndUpdatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsDirect($scoreId: String!, $limit: Int!) {
              listItemByScoreIdAndUpdatedAt(
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
                  scoreResults {
                    items {
                      id
                      value
                      explanation
                      confidence
                      scorecardId
                      scoreId
                      scorecard {
                        id
                        name
                      }
                      score {
                        id
                        name
                      }
                      updatedAt
                      createdAt
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
          
          console.log('Direct GraphQL query response for items:', JSON.stringify(directQuery, null, 2));
          
          if (directQuery.data?.listItemByScoreIdAndUpdatedAt?.items) {
            console.log(`Found ${directQuery.data.listItemByScoreIdAndUpdatedAt.items.length} items via direct GraphQL query`);
            // No need to sort as the GSI already returns items sorted by updatedAt
            itemsFromDirectQuery = directQuery.data.listItemByScoreIdAndUpdatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByScoreIdAndUpdatedAt.nextToken;
          } else {
            console.warn('No items found in direct GraphQL query response');
          }
        } else if (useScorecard) {
          // If only a scorecard is selected, filter by scorecardId
          console.log('Attempting direct GraphQL query for items with scorecardId:', selectedScorecard);
          const directQuery = await graphqlRequest<{ listItemByScorecardIdAndUpdatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsDirect($scorecardId: String!, $limit: Int!) {
              listItemByScorecardIdAndUpdatedAt(
                scorecardId: $scorecardId, 
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
                  scoreResults {
                    items {
                      id
                      value
                      explanation
                      confidence
                      scorecardId
                      scoreId
                      scorecard {
                        id
                        name
                      }
                      score {
                        id
                        name
                      }
                      updatedAt
                      createdAt
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
          
          console.log('Direct GraphQL query response for items:', JSON.stringify(directQuery, null, 2));
          
          if (directQuery.data?.listItemByScorecardIdAndUpdatedAt?.items) {
            console.log(`Found ${directQuery.data.listItemByScorecardIdAndUpdatedAt.items.length} items via direct GraphQL query`);
            // No need to sort as the GSI already returns items sorted by updatedAt
            itemsFromDirectQuery = directQuery.data.listItemByScorecardIdAndUpdatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByScorecardIdAndUpdatedAt.nextToken;
          } else {
            console.warn('No items found in direct GraphQL query response');
          }
        } else {
          // If neither scorecard nor score is selected, filter by accountId
          console.log('Attempting direct GraphQL query for items with accountId:', accountId);
          const directQuery = await graphqlRequest<{ listItemByAccountIdAndUpdatedAt: { items: any[], nextToken: string | null } }>(`
            query ListItemsDirect($accountId: String!, $limit: Int!) {
              listItemByAccountIdAndUpdatedAt(
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
                  scoreResults {
                    items {
                      id
                      value
                      explanation
                      confidence
                      scorecardId
                      scoreId
                      scorecard {
                        id
                        name
                      }
                      score {
                        id
                        name
                      }
                      updatedAt
                      createdAt
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
          
          console.log('Direct GraphQL query response for items:', JSON.stringify(directQuery, null, 2));
          
          if (directQuery.data?.listItemByAccountIdAndUpdatedAt?.items) {
            console.log(`Found ${directQuery.data.listItemByAccountIdAndUpdatedAt.items.length} items via direct GraphQL query`);
            // No need to sort as the GSI already returns items sorted by updatedAt
            itemsFromDirectQuery = directQuery.data.listItemByAccountIdAndUpdatedAt.items;
            nextTokenFromDirectQuery = directQuery.data.listItemByAccountIdAndUpdatedAt.nextToken;
          } else {
            console.warn('No items found in direct GraphQL query response');
          }
        }
      } catch (error) {
        console.error('Error in direct GraphQL query:', error);
      }
      
      // Use the items from the direct query
      const itemsToUse = itemsFromDirectQuery;
      const nextTokenToUse = nextTokenFromDirectQuery;
      
      // If no items are found, we'll log this information
      if (itemsToUse.length === 0) {
        console.log('No items found for this account. You may need to create some items first.');
      }
      
      // Transform the data to match the expected format
      const transformedItems = itemsToUse.map(item => {
        // Group scoreResults by scorecard
        const groupedScoreResults: GroupedScoreResults = {};
        
        console.log('Raw item before transformation:', {
          id: item.id,
          externalId: item.externalId,
          accountId: item.accountId,
          scoreId: item.scoreId,
          hasScoreResults: !!item.scoreResults,
          scoreResultsItemsCount: item.scoreResults?.items?.length,
          firstScoreResult: item.scoreResults?.items?.[0] 
        });
        
        if (item.scoreResults && item.scoreResults.items) {
          item.scoreResults.items.forEach((result: any) => {
            if (result.scorecardId) {
              // Create scorecard entry if it doesn't exist
              if (!groupedScoreResults[result.scorecardId]) {
                groupedScoreResults[result.scorecardId] = {
                  scorecardName: result.scorecard?.name || `Scorecard ${result.scorecardId.substring(0, 8)}`,
                  scores: []
                };
              }
              
              // Add score to the scorecard's scores if not already present
              const scoreExists = groupedScoreResults[result.scorecardId].scores.some(
                s => s.scoreId === result.scoreId
              );
              
              if (!scoreExists && result.scoreId) {
                groupedScoreResults[result.scorecardId].scores.push({
                  scoreId: result.scoreId,
                  scoreName: result.score?.name || `Score ${result.scoreId.substring(0, 8)}`
                });
              }
            }
          });
        } else if (item.scorecardId && !Object.keys(groupedScoreResults).length) {
          // If item has a scorecardId but no scoreResults, create a placeholder entry
          console.log('Item has scorecardId but no scoreResults:', item.scorecardId);
          
          // Try to add a placeholder entry using the scorecardId
          groupedScoreResults[item.scorecardId] = {
            scorecardName: `Scorecard ${item.scorecardId.substring(0, 8)}`,
            scores: []
          };
          
          // Add score if available
          if (item.scoreId) {
            groupedScoreResults[item.scorecardId].scores.push({
              scoreId: item.scoreId,
              scoreName: `Score ${item.scoreId.substring(0, 8)}`
            });
          }
        }
        
        console.log('Generated groupedScoreResults:', groupedScoreResults);
        
        // Get the primary scorecard and score name to display
        let primaryScorecardName = null;
        let primaryScoreName = null;
        
        // Logic to determine primary scorecard (first one with scores, or just first one)
        const scorecardIds = Object.keys(groupedScoreResults);
        if (scorecardIds.length > 0) {
          const firstScorecardWithScores = scorecardIds.find(
            id => groupedScoreResults[id].scores.length > 0
          ) || scorecardIds[0];
          
          primaryScorecardName = groupedScoreResults[firstScorecardWithScores].scorecardName;
          
          // Get first score if any exist
          if (groupedScoreResults[firstScorecardWithScores].scores.length > 0) {
            primaryScoreName = groupedScoreResults[firstScorecardWithScores].scores[0].scoreName;
          }
        }
        
        // Create the transformed item with all required fields
        const transformedItem = {
          id: item.id,
          accountId: item.accountId,
          externalId: item.externalId,
          description: item.description,
          evaluationId: item.evaluationId,
          updatedAt: item.updatedAt,
          createdAt: item.createdAt,
          isEvaluation: item.isEvaluation,
          // UI compatibility fields
          scorecard: primaryScorecardName,
          score: primaryScoreName,
          date: item.updatedAt || item.createdAt,
          status: "Done", // Default status
          results: 0,
          inferences: 0,
          cost: "$0.000",
          isNew: true, // Mark all items as new for animation
          // Add grouped scoreResults
          groupedScoreResults: groupedScoreResults
        } as Item;
        
        console.log('Final transformed item:', {
          id: transformedItem.id,
          primaryScorecard: transformedItem.scorecard,
          primaryScore: transformedItem.score,
          groupedScoreResultsKeys: Object.keys(transformedItem.groupedScoreResults || {})
        });
        
        return transformedItem;
      });
      
      setItems(transformedItems);
      setNextToken(nextTokenToUse);
      
      // After a delay, remove the "isNew" flag
      setTimeout(() => {
        setItems(prevItems => 
          prevItems.map(item => 
            item.isNew ? { ...item, isNew: false } : item
          )
        );
      }, 3000); // Remove the flag after 3 seconds
      
      setIsLoading(false);
    } catch (error) {
      console.error('Error fetching items:', error);
      setIsLoading(false);
    }
  }, [user, amplifyClient, selectedAccount, setItems, setIsLoading, setNextToken, selectedScorecard, selectedScore]);
  
  // Initial data load
  useEffect(() => {
    fetchItems();
  }, [user, fetchItems, selectedAccount, selectedScorecard, selectedScore]);
  
  // Set up subscription for item creations
  useEffect(() => {
    if (!selectedAccount) return;
    
    console.log('Setting up item creation subscription for account:', selectedAccount.id);
    
    const subscription = observeItemCreations().subscribe({
      next: async ({ data: newItem }) => {
        // Skip if we received null data (common with Amplify Gen2)
        if (!newItem) {
          console.log('Received null item data from subscription - ignoring');
          return;
        }
        
        console.log('New item created notification received:', newItem);
        
        if (newItem.accountId === selectedAccount.id) {
          // Set loading state while we fetch
          setIsLoading(true);
          
          try {
            // Immediately fetch updated items list
            await fetchItems();
            console.log('Successfully fetched updated items after new item creation');
          } catch (error) {
            console.error('Error fetching updated items:', error);
            
            // As a fallback, manually add the new item to the state
            setItems(prevItems => {
              // Check if the item already exists in the list
              const exists = prevItems.some(item => item.id === newItem.id);
              if (exists) {
                return prevItems;
              }
              
              // Create a new item with the UI compatibility fields
              const newItemWithUIFields: Item = {
                id: newItem.id,
                accountId: newItem.accountId,
                externalId: newItem.externalId || undefined,
                description: newItem.description || undefined,
                scorecardId: newItem.scorecardId || undefined,
                scoreId: newItem.scoreId || undefined,
                evaluationId: newItem.evaluationId || undefined,
                updatedAt: newItem.updatedAt || undefined,
                createdAt: newItem.createdAt || undefined,
                isEvaluation: newItem.isEvaluation,
                // UI compatibility fields
                scorecard: newItem.scorecardId ? `Scorecard ${newItem.scorecardId.substring(0, 8)}` : undefined,
                score: newItem.scoreId ? `Score ${newItem.scoreId.substring(0, 8)}` : undefined,
                date: (newItem.updatedAt || newItem.createdAt) || undefined,
                status: "Done",
                results: 0,
                inferences: 0,
                cost: "$0.000",
                isNew: true // Mark as new for animation
              };
              
              // Add the new item to the beginning of the list
              return [newItemWithUIFields, ...prevItems];
            });
            
            // After a delay, remove the "isNew" flag from the newly added item
            setTimeout(() => {
              setItems(prevItems => 
                prevItems.map(item => 
                  item.id === newItem.id ? { ...item, isNew: false } : item
                )
              );
            }, 3000); // Remove the flag after 3 seconds
          } finally {
            setIsLoading(false);
          }
        }
      },
      error: (error) => {
        console.error('Error in item creation subscription:', error);
      }
    });
    
    itemSubscriptionRef.current = subscription;
    
    return () => {
      console.log('Cleaning up item creation subscription');
      if (itemSubscriptionRef.current) {
        itemSubscriptionRef.current.unsubscribe();
        itemSubscriptionRef.current = null;
      }
    };
  }, [selectedAccount, fetchItems]);

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
    console.log("Filtering items:", {
      itemsCount: items.length,
      selectedScorecard,
      selectedScore,
      filterConfigLength: filterConfig.length
    });
    
    return items.filter(item => {
      if (!selectedScorecard && !selectedScore && filterConfig.length === 0) return true
      
      // Check for scorecard and score matches
      let scorecardMatch = !selectedScorecard || item.scorecardId === selectedScorecard
      let scoreMatch = !selectedScore || item.scoreId === selectedScore
      
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
          </>
        )}
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

  // Add a useEffect for the intersection observer
  useEffect(() => {
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
    
    // Observe the load more element if it exists
    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    // Cleanup
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [nextToken, isLoadingMore, handleLoadMore]); // Add handleLoadMore to dependencies

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
            />
          </div>
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
        )}
      </div>
    </div>
  );
}


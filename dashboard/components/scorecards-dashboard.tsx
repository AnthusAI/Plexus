"use client"
import React, { useState, useEffect } from "react"
import { Button } from "./ui/button"
import { amplifyClient, getClient } from "@/utils/amplify-client"
import type { Schema } from "@/amplify/data/resource"
import type { AuthModeStrategyType } from "aws-amplify/datastore"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu"
import { 
  Activity, 
  Pencil, 
  MoreHorizontal,
  Plus,
  Database,
  Columns2,
  Square,
  X,
  MessageCircleMore,
  Coins
} from "lucide-react"
import { ScoreCount } from "./scorecards/score-count"
import { CardButton } from "./CardButton"
import { listFromModel } from "@/utils/amplify-helpers"
import { AmplifyListResult } from '@/types/shared'
import { graphqlRequest } from "@/utils/amplify-client"
import { generateClient } from "aws-amplify/data"
import ScorecardComponent from "./scorecards/ScorecardComponent"
import ScorecardGrid from "./scorecards/ScorecardGrid"
import { cn } from "@/lib/utils"
import { ScoreComponent } from "./ui/score-component"
import { ItemComponent, type ItemData } from "./ui/item-component"
import ScorecardDetailView from "./scorecards/ScorecardDetailView"
import { useRouter, usePathname, useParams } from "next/navigation"
import { ScorecardDashboardSkeleton } from "./loading-skeleton"
import { Task, TaskHeader, TaskContent } from "./Task"
import { observeTaskUpdates, observeTaskStageUpdates } from "@/utils/subscriptions"
import { AdHocFeedbackAnalysis } from "@/components/ui/ad-hoc-feedback-analysis"
import { AdHocCostAnalysis } from "@/components/ui/ad-hoc-cost-analysis"
import { motion, AnimatePresence } from 'framer-motion'

const ACCOUNT_KEY = 'call-criteria'

export default function ScorecardsComponent({
  initialSelectedScorecardId = null,
  initialSelectedScoreId = null,
  initialSelectedVersionId = null
}: {
  initialSelectedScorecardId?: string | null,
  initialSelectedScoreId?: string | null,
  initialSelectedVersionId?: string | null
} = {}) {
  // Get the Amplify client for Tasks model
  const client = getClient();
  
  const [scorecards, setScorecards] = useState<Schema['Scorecard']['type'][]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedScorecard, setSelectedScorecard] = useState<Schema['Scorecard']['type'] | null>(null)
  const [selectedScore, setSelectedScore] = useState<{
    id: string
    name: string
    key: string
    description: string
    order: number
    type: string
    sectionId: string
    externalId?: string
  } | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(initialSelectedVersionId)
  const [selectedScorecardSections, setSelectedScorecardSections] = useState<{
    items: Array<{
      id: string
      name: string
      order: number
      scores: {
        items: Array<{
          id: string
          name: string
          key: string
          description: string
          order: number
          type: string
        }>
      }
    }>
  } | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(!!initialSelectedScorecardId)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(40)
  const [scorecardScoreCounts, setScorecardScoreCounts] = useState<Record<string, number>>({})
  const [scorecardCountsLoading, setScorecardCountsLoading] = useState<Record<string, boolean>>({})
  const [scorecardDetailWidth, setScorecardDetailWidth] = useState(50)
  const [maximizedScoreId, setMaximizedScoreId] = useState<string | null>(null)
  const [selectedItem, setSelectedItem] = useState<any | null>(null)
  const [isCreatingItem, setIsCreatingItem] = useState(false)
  const [scorecardExamples, setScorecardExamples] = useState<string[]>([])
  const [shouldExpandExamples, setShouldExpandExamples] = useState(false)
  const [selectedTask, setSelectedTask] = useState<any | null>(null)
  const [isTaskViewActive, setIsTaskViewActive] = useState(false)
  const [feedbackAnalysisPanel, setFeedbackAnalysisPanel] = useState<{
    isOpen: boolean;
    scorecardId?: string;
    scoreId?: string;
    scoreName?: string;
    type: 'scorecard' | 'score';
  } | null>(null)
  const [costAnalysisPanel, setCostAnalysisPanel] = useState<{
    isOpen: boolean;
    scorecardId?: string;
    scoreId?: string;
    type: 'scorecard' | 'score';
  } | null>(null)
  const router = useRouter()
  const pathname = usePathname()
  
  // Ref map to track scorecard elements for scroll-to-view functionality
  const scorecardRefsMap = React.useRef<Map<string, HTMLDivElement | null>>(new Map())
  
  // Function to scroll to a selected scorecard
  const scrollToSelectedScorecard = React.useCallback((scorecardId: string) => {
    // Use requestAnimationFrame to ensure the layout has updated after selection
    requestAnimationFrame(() => {
      const scorecardElement = scorecardRefsMap.current.get(scorecardId);
      if (scorecardElement) {
        scorecardElement.scrollIntoView({
          behavior: 'smooth',
          block: 'start', // Align to the top of the container
          inline: 'nearest'
        });
      }
    });
  }, []);
  
  const params = useParams()

  // Handle deep linking - check if we're on a specific scorecard or score page
  useEffect(() => {
    console.log('🔵 Deep linking useEffect triggered:', {
      initialSelectedScorecardId,
      scorecardsCount: scorecards.length,
      scorecardIds: scorecards.map(sc => sc.id)
    });
    
    if (initialSelectedScorecardId) {
      // Find the scorecard in the list
      const scorecard = scorecards.find(sc => sc.id === initialSelectedScorecardId);
      console.log('🔵 Looking for scorecard in deep linking:', {
        targetId: initialSelectedScorecardId,
        found: !!scorecard,
        foundScorecard: scorecard ? {
          id: scorecard.id,
          name: scorecard.name,
          hasExampleItems: 'exampleItems' in scorecard
        } : null
      });
      
      if (scorecard) {
        handleSelectScorecard(scorecard);
      }
    }
  }, [initialSelectedScorecardId, scorecards]);

  // Handle deep linking for score selection - runs after scorecard sections are loaded
  useEffect(() => {
    if (initialSelectedScoreId && selectedScorecardSections) {
      // Find the score in the sections
      for (const section of selectedScorecardSections.items) {
        const score = section.scores.items.find(s => s.id === initialSelectedScoreId);
        if (score) {
          handleScoreSelect({...score, sectionId: section.id}, section.id, initialSelectedVersionId || undefined);
          break;
        }
      }
    }
  }, [initialSelectedScoreId, selectedScorecardSections, initialSelectedVersionId]);

  // Handle browser back/forward navigation with popstate event
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      // Extract scorecard ID from URL if present
      const scorecardMatch = window.location.pathname.match(/\/lab\/scorecards\/([^\/]+)(?:\/|$)/);
      const scorecardIdFromUrl = scorecardMatch ? scorecardMatch[1] : null;
      
      // Extract score ID from URL if present
      const scoreMatch = window.location.pathname.match(/\/lab\/scorecards\/[^\/]+\/scores\/([^\/]+)(?:\/versions\/([^\/]+))?$/);
      const scoreIdFromUrl = scoreMatch ? scoreMatch[1] : null;
      const versionIdFromUrl = scoreMatch ? scoreMatch[2] : null;
      
      if (scorecardIdFromUrl) {
        // Find the scorecard in the list
        const scorecard = scorecards.find(sc => sc.id === scorecardIdFromUrl);
        if (scorecard) {
          setSelectedScorecard(scorecard);
          if (isNarrowViewport) {
            setIsFullWidth(true);
          }
          
          // If we also have a score ID, select that score
          if (scoreIdFromUrl && selectedScorecardSections) {
            for (const section of selectedScorecardSections.items) {
              const score = section.scores.items.find(s => s.id === scoreIdFromUrl);
              if (score) {
                setSelectedScore({...score, sectionId: section.id});
                // Also set the version ID if present in URL
                setSelectedVersionId(versionIdFromUrl);
                break;
              }
            }
          } else {
            setSelectedScore(null);
            setSelectedVersionId(null);
          }
        }
      } else {
        setSelectedScorecard(null);
        setSelectedScore(null);
        setSelectedVersionId(null);
        if (isNarrowViewport) {
          setIsFullWidth(false);
        }
      }
    };

    // Add event listener for popstate (browser back/forward)
    window.addEventListener('popstate', handlePopState);
    
    // Clean up event listener on unmount
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, [scorecards, selectedScorecardSections, isNarrowViewport]);

  // Task monitoring with real-time subscriptions
  useEffect(() => {
    if (!selectedTask) return;

    console.log('Setting up task subscriptions for task:', selectedTask.id);

    const taskSubscription = observeTaskUpdates().subscribe({
      next: (value: any) => {
        const { type, data } = value;
        if (data?.id === selectedTask.id) {
          console.log(`Task ${type} update for ${selectedTask.id}:`, data);
          setSelectedTask((prev: any) => prev ? { ...prev, ...data } : data);
        }
      },
      error: (error: any) => {
        console.error('Task subscription error:', error);
      }
    });

    const stageSubscription = observeTaskStageUpdates().subscribe({
      next: (value: any) => {
        const { type, data } = value;
        if (data?.taskId === selectedTask.id) {
          console.log(`TaskStage ${type} update for task ${selectedTask.id}:`, data);
          setSelectedTask((prev: any) => {
            if (!prev) return prev;
            
            const updatedStages = prev.stages ? [...prev.stages] : [];
            const existingStageIndex = updatedStages.findIndex((stage: any) => stage.id === data.id);
            
            if (existingStageIndex >= 0) {
              updatedStages[existingStageIndex] = { ...updatedStages[existingStageIndex], ...data };
            } else {
              updatedStages.push(data);
            }
            
            const updatedTask = {
              ...prev,
              stages: updatedStages.sort((a: any, b: any) => a.order - b.order),
              currentStageName: data.status === 'RUNNING' ? data.name : prev.currentStageName
            };

            console.log('Updated task with stages:', {
              taskId: updatedTask.id,
              stagesCount: updatedTask.stages?.length,
              currentStageName: updatedTask.currentStageName,
              stages: updatedTask.stages
            });

            return updatedTask;
          });
        }
      },
      error: (error: any) => {
        console.error('TaskStage subscription error:', error);
      }
    });

    return () => {
      console.log('Cleaning up task subscriptions');
      taskSubscription.unsubscribe();
      stageSubscription.unsubscribe();
    };
  }, [selectedTask?.id]);

  // Handle task creation and monitoring
  const handleTaskCreated = (task: any) => {
    console.log('Task created in scorecard dashboard:', task);
    setSelectedTask(task);
    setIsTaskViewActive(true);
    
    // Move to two-column layout
    if (selectedScore) {
      // Reset score maximization to show two columns
      setMaximizedScoreId(null);
    }
    
    // If we have a selected item, clear it to make room for the task
    if (selectedItem) {
      setSelectedItem(null);
      setIsCreatingItem(false);
    }
  };

  // Handle opening feedback analysis for a scorecard
  const handleScorecardFeedbackAnalysis = (scorecardId: string) => {
    console.log('Opening feedback analysis for scorecard:', scorecardId);
    setFeedbackAnalysisPanel({
      isOpen: true,
      scorecardId,
      type: 'scorecard'
    });
    // Close task view if open
    setIsTaskViewActive(false);
    // If we have a selected score, clear it to show scorecard + feedback layout
    if (selectedScore) {
      setSelectedScore(null);
      setMaximizedScoreId(null);
    }
  };

  // Handle opening cost analysis for a scorecard
  const handleScorecardCostAnalysis = (scorecardId: string) => {
    console.log('Opening cost analysis for scorecard:', scorecardId);
    setCostAnalysisPanel({ isOpen: true, scorecardId, type: 'scorecard' });
    setIsTaskViewActive(false);
    if (selectedScore) {
      setSelectedScore(null);
      setMaximizedScoreId(null);
    }
  };

  const handleScoreCostAnalysis = (scoreId: string, scorecardId?: string) => {
    console.log('Opening cost analysis for score:', scoreId);
    setCostAnalysisPanel({ isOpen: true, scoreId, scorecardId, type: 'score' });
    setIsTaskViewActive(false);
  };

  // Handle opening feedback analysis for a specific score
  const handleScoreFeedbackAnalysis = (scoreId: string, scoreName?: string, scorecardId?: string) => {
    console.log('Opening feedback analysis for score:', scoreId);
    setFeedbackAnalysisPanel({
      isOpen: true,
      scoreId,
      scoreName,
      scorecardId,
      type: 'score'
    });
    // Close task view if open
    setIsTaskViewActive(false);
  };

  // Handle closing feedback analysis panel
  const handleCloseFeedbackAnalysis = () => {
    setFeedbackAnalysisPanel(null);
  };

  // Handle task closure
  const handleCloseTask = () => {
    setSelectedTask(null);
    setIsTaskViewActive(false);
  };

  // Custom setter for selectedScorecard that handles both state and URL
  const handleSelectScorecard = async (scorecard: Schema['Scorecard']['type'] | null) => {
    console.log('🔵 handleSelectScorecard called:', {
      newScorecardName: scorecard?.name,
      currentScorecardId: selectedScorecard?.id,
      willUpdate: scorecard?.id !== selectedScorecard?.id
    });

    // Only update state if the selected scorecard has changed
    if (scorecard?.id !== selectedScorecard?.id) {
      console.log('🔵 Scorecard selection changed, updating state...');
      
      // IMMEDIATE STATE UPDATES - Show the new scorecard instantly
      // Close any open panels
      if (costAnalysisPanel?.isOpen) {
        setCostAnalysisPanel(null);
      }
      
      // Update scorecard immediately
      setSelectedScorecard(scorecard);
      
      // Clear old data immediately to avoid showing wrong scores
      setSelectedScore(null);
      setSelectedVersionId(null); // Clear version when changing scorecards
      setSelectedScorecardSections(null); // Clear old sections immediately
      setScorecardExamples([]); // Clear old examples
      setShouldExpandExamples(false);
      
      // Update URL immediately
      if (scorecard && (!initialSelectedScoreId || initialSelectedScorecardId !== scorecard.id)) {
        const newPathname = `/lab/scorecards/${scorecard.id}`;
        window.history.pushState(null, '', newPathname);
      } else if (!scorecard) {
        window.history.pushState(null, '', '/lab/scorecards');
      }
      
      // Scroll to the selected scorecard
      if (scorecard) {
        setTimeout(() => {
          scrollToSelectedScorecard(scorecard.id);
        }, 100);
      }
      
      if (scorecard && isNarrowViewport) {
        setIsFullWidth(true);
      }
      
      // PROGRESSIVE LOADING - Load data in the background
      if (scorecard && scorecard.id) {
        console.log('🔵 Starting progressive data load for scorecard:', scorecard.name);
        
        // Start loading data progressively without blocking the UI
        setTimeout(async () => {
          try {
            // Check if we already have some data from the progressive loading
            const existingScorecard = scorecards.find(sc => sc.id === scorecard.id);
            const hasExistingExamples = existingScorecard && (existingScorecard as any).examples?.length > 0;
            
            console.log('🔄 Loading scorecard data in parallel...');
            
            // Start all data loading operations in parallel
            const dataPromises = [];
            
            // Example items promise
            let exampleItemsPromise;
            if (hasExistingExamples) {
              console.log('🚀 Using cached example items');
              setScorecardExamples((existingScorecard as any).examples);
              exampleItemsPromise = Promise.resolve();
            } else {
              exampleItemsPromise = graphqlRequest<{
                listScorecardExampleItemByScorecardId: {
                  items: Array<{
                    itemId: string;
                    item: {
                      id: string;
                      externalId?: string;
                      description?: string;
                      text?: string;
                      updatedAt?: string;
                      createdAt?: string;
                    };
                  }>;
                };
              }>(`
                query ListExampleItemsByScorecardId($scorecardId: ID!) {
                  listScorecardExampleItemByScorecardId(scorecardId: $scorecardId) {
                    items {
                      itemId
                      item {
                        id
                        externalId
                        description
                        text
                        updatedAt
                        createdAt
                      }
                    }
                  }
                }
              `, { scorecardId: scorecard.id }).then(itemAssociationsResult => {
                const exampleItems = (itemAssociationsResult.data?.listScorecardExampleItemByScorecardId?.items || [])
                  .map(association => association.item)
                  .filter(item => item !== null)
                  .sort((a, b) => {
                    const dateA = new Date(a.updatedAt || a.createdAt || '').getTime();
                    const dateB = new Date(b.updatedAt || b.createdAt || '').getTime();
                    return dateB - dateA;
                  });
                  
                const exampleItemsFormatted = exampleItems.map(item => `item:${item.id}`);
                setScorecardExamples(exampleItemsFormatted);
                console.log('✅ Example items loaded');
              }).catch(error => {
                console.warn('Failed to load example items:', error);
              });
            }
            
            // Sections promise
            const sectionsPromise = amplifyClient.ScorecardSection.list({
              filter: { scorecardId: { eq: scorecard.id } }
            });
            
            // Wait for both to complete
            const [sectionsResult] = await Promise.all([
              sectionsPromise,
              exampleItemsPromise
            ]);
            
            const sections = sectionsResult.data || [];
            
            if (sections.length === 0) {
              console.log('⚠️ No sections found for scorecard');
              setSelectedScorecardSections({ items: [] });
              return;
            }
            
            // Load scores for all sections in parallel
            console.log('🔄 Loading scores for all sections in parallel...');
            const transformedSections = {
              items: await Promise.all(sections.map(async section => {
                try {
                  const allScores = await fetchAllScoresForSection(section.id);
                  return {
                    id: section.id,
                    name: section.name,
                    order: section.order,
                    scores: {
                      items: allScores.map(score => ({
                        id: score.id,
                        name: score.name,
                        key: score.key || '',
                        description: score.description || '',
                        order: score.order,
                        type: score.type,
                        externalId: score.externalId,
                      }))
                    }
                  };
                } catch (error) {
                  console.warn(`Failed to load scores for section ${section.name}:`, error);
                  return {
                    id: section.id,
                    name: section.name,
                    order: section.order,
                    scores: { items: [] }
                  };
                }
              }))
            };
            
            // Update sections with loaded data
            setSelectedScorecardSections(transformedSections);
            console.log('✅ All scorecard data loaded in parallel');
            
          } catch (error) {
            console.error('Error loading scorecard data:', error);
            setError(error as Error);
            // Set empty sections so UI doesn't hang
            setSelectedScorecardSections({ items: [] });
          }
        }, 0); // Start immediately but non-blocking
      } else {
        setSelectedScorecardSections(null);
      }
    }
  };

  // Custom setter for selectedScore that handles both state and URL
  const handleScoreSelect = (score: any, sectionId: string, versionId?: string) => {
    // Only update state if the selected score has changed
    if (score?.id !== selectedScore?.id) {
      setSelectedScore({...score, sectionId});
      // Reset item selection when selecting a score
      setSelectedItem(null);
      setIsCreatingItem(false);
      // Close any open Cost Analysis when selecting a new score
      if (costAnalysisPanel?.isOpen) {
        setCostAnalysisPanel(null);
      }
      
      // Close feedback analysis if open when selecting a score
      if (feedbackAnalysisPanel?.isOpen) {
        setFeedbackAnalysisPanel(null);
      }
      
      // Set version ID if provided
      if (versionId) {
        setSelectedVersionId(versionId);
      } else {
        // Clear version when selecting a new score without specifying version
        setSelectedVersionId(null);
      }
      
      // Update URL without triggering a navigation/re-render
      if (selectedScorecard) {
        let newPathname = `/lab/scorecards/${selectedScorecard.id}/scores/${score.id}`;
        if (versionId) {
          newPathname += `/versions/${versionId}`;
        }
        window.history.pushState(null, '', newPathname);
      }
    }
  };

  // Handle version selection
  const handleVersionSelect = (versionId: string) => {
    setSelectedVersionId(versionId);
    
    // Update URL to include version
    if (selectedScorecard && selectedScore) {
      const newPathname = `/lab/scorecards/${selectedScorecard.id}/scores/${selectedScore.id}/versions/${versionId}`;
      window.history.pushState(null, '', newPathname);
    }
  };

  // Handle editing an existing item
  const handleEditItem = async (itemId: string) => {
    try {
      const result = await amplifyClient.Item.get({ id: itemId });
      if (result.data) {
        const itemData: ItemData = {
          id: result.data.id,
          externalId: result.data.externalId || '',
          description: result.data.description || '',
          text: result.data.text || '',
          metadata: (result.data.metadata && typeof result.data.metadata === 'object' && !Array.isArray(result.data.metadata)) 
            ? result.data.metadata as Record<string, string> 
            : {},
          attachedFiles: Array.isArray(result.data.attachedFiles) 
            ? result.data.attachedFiles.filter((file): file is string => typeof file === 'string')
            : [],
          accountId: result.data.accountId,
          isEvaluation: result.data.isEvaluation
        };
        
        setSelectedItem(itemData);
        setIsCreatingItem(false); // This is an edit, not a creation
        // Reset score selection when editing an item
        setSelectedScore(null);
        setMaximizedScoreId(null);
      }
    } catch (error) {
      console.error('Error loading item for editing:', error);
    }
  };

  // Handle creating a new item
  const handleCreateItem = (initialContent?: string) => {
    const newItem: ItemData = {
      id: '', // Will be set when saved
      externalId: '',
      description: '',
      text: initialContent || '',
      metadata: {},
      attachedFiles: [],
      accountId: accountId || '',
      isEvaluation: false
    };
    
    setSelectedItem(newItem);
    setIsCreatingItem(true);
    // Reset score selection when creating an item
    setSelectedScore(null);
    setMaximizedScoreId(null);
  };

  // Handle saving an item
  const handleSaveItem = async (item: ItemData) => {
    try {
      if (item.id) {
        // Update existing item
        const updateInput: {
          id: string;
          externalId?: string;
          description?: string;
          text?: string;
          metadata?: string;
          attachedFiles?: string[];
        } = {
          id: item.id
        };

        // Add optional fields only if they have values
        if (item.externalId) updateInput.externalId = item.externalId;
        if (item.description) updateInput.description = item.description;
        if (item.text) updateInput.text = item.text;
        if (item.metadata && Object.keys(item.metadata).length > 0) {
          updateInput.metadata = JSON.stringify(item.metadata);
        }
        if (item.attachedFiles && item.attachedFiles.length > 0) {
          updateInput.attachedFiles = item.attachedFiles;
        }

        const result = await (client.models.Item.update as any)(updateInput);
        console.log('Item updated successfully:', result.data?.id);
        
        // Update the local state with the saved item
        setSelectedItem({ ...item, ...result.data });
      } else {
        // Create new item
        const createInput: {
          externalId?: string;
          description?: string;
          text?: string;
          metadata?: string;
          attachedFiles?: string[];
          accountId: string;
          isEvaluation: boolean;
          createdByType?: string;
        } = {
          accountId: item.accountId || accountId!,
          isEvaluation: item.isEvaluation || false,
          createdByType: 'prediction' // Dashboard-created items are predictions, not evaluations
        };

        // Add optional fields only if they have values
        if (item.externalId) createInput.externalId = item.externalId;
        if (item.description) createInput.description = item.description;
        if (item.text) createInput.text = item.text;
        if (item.metadata && Object.keys(item.metadata).length > 0) {
          createInput.metadata = JSON.stringify(item.metadata);
        }
        if (item.attachedFiles && item.attachedFiles.length > 0) {
          createInput.attachedFiles = item.attachedFiles;
        }
        
        console.log('Creating item with input:', createInput);
        console.log('Metadata value type and content:', {
          hasMetadata: 'metadata' in createInput,
          metadataType: typeof createInput.metadata,
          metadataValue: createInput.metadata
        });
        
        const result = await (client.models.Item.create as any)(createInput);
        console.log('Full result object:', result);
        console.log('Result data:', result.data);
        console.log('Result errors:', result.errors);
        console.log('Item created successfully:', result.data?.id);
        
        // Check if the creation actually succeeded
        if (!result.data?.id) {
          console.error('Item creation failed - no ID returned:', result);
          throw new Error('Item creation failed: No ID returned from server');
        }

        // Create ScorecardExampleItem association if we have a selected scorecard
        if (selectedScorecard?.id && result.data.id) {
          try {
            // Use the amplifyClient wrapper which is working correctly
            console.log('Creating ScorecardExampleItem association using amplifyClient wrapper...');
            const associationResult = await amplifyClient.ScorecardExampleItem.create({
              itemId: result.data.id,
              scorecardId: selectedScorecard.id,
              addedAt: new Date().toISOString()
            });
            console.log('ItemScorecard association result:', associationResult);
            
            // Verify the association was actually created
            if (!associationResult.data?.id) {
              throw new Error('Association creation failed: No ID returned');
            }
          } catch (associationError) {
            console.error('Error creating ScorecardExampleItem association:', associationError);
            // This is a critical error - throw it so user knows the association failed
            throw new Error(`Item created but failed to associate with scorecard: ${associationError instanceof Error ? associationError.message : 'Unknown error'}`);
          }
        }
        
        // Update the item with the new ID and mark it as no longer being created
        setSelectedItem({ ...item, id: result.data.id });
        setIsCreatingItem(false);
        
        // Signal that we should expand the examples section
        setShouldExpandExamples(true);
        
        // Refresh the scorecard data to show the newly associated item
        if (selectedScorecard?.id) {
          console.log('Refreshing scorecard data after item creation...');
          const updatedScorecards = await fetchScorecards();
          console.log('Scorecard data refreshed, checking if new item appears...');
          
          // Update the selected scorecard with the refreshed data
          if (updatedScorecards) {
            const refreshedScorecard = updatedScorecards.find(s => s.id === selectedScorecard.id);
            if (refreshedScorecard) {
              console.log('Updating selected scorecard with refreshed data...');
              console.log('Refreshed scorecard examples:', (refreshedScorecard as any).examples);
              
              // Update both the selected scorecard and the examples state
              setSelectedScorecard(refreshedScorecard);
              
              // Update the scorecardExamples state directly from the refreshed data
              const refreshedExamples = (refreshedScorecard as any).examples || [];
              console.log('Setting scorecardExamples to:', refreshedExamples);
              setScorecardExamples(refreshedExamples);
              
              console.log('Selected scorecard and examples updated, new item should now appear');
            }
          }
        }
        
        // Optionally, you could also refresh the scorecard data here if you want to show
        // the newly created item in the scorecard's example items section
      }
      
      return true; // Indicate success
    } catch (error) {
      console.error('Error saving item:', error);
      // Provide more specific error information
      if (error instanceof Error) {
        throw new Error(`Failed to save item: ${error.message}`);
      } else {
        throw new Error('Failed to save item: Unknown error occurred');
      }
    }
  };

  // Handle creating a new score
  const handleCreateScore = async (sectionId: string) => {
    if (!selectedScorecard || !accountId) {
      console.error('No selected scorecard or accountId for score creation');
      return;
    }

    try {
      console.log('Creating score in section:', sectionId);
      console.log('Selected scorecard:', selectedScorecard.id, selectedScorecard.name);
      console.log('Available sections:', selectedScorecardSections?.items.map(s => ({id: s.id, name: s.name})));
      
      // Get the next order number for this section
      const section = selectedScorecardSections?.items.find(s => s.id === sectionId);
      console.log('Target section found:', section);
      const existingScoresCount = section?.scores?.items?.length || 0;
      const nextOrder = existingScoresCount + 1;

      // Create a new score
      const newScoreData = await amplifyClient.Score.create({
        name: 'New Score',
        type: 'Score',
        order: nextOrder,
        sectionId: sectionId,
        scorecardId: selectedScorecard.id,
        externalId: `score_${Date.now()}` // Generate a unique external ID
      });

      if (!newScoreData.data) {
        console.error('Failed to create score - no data returned');
        return;
      }

      console.log('✅ Score created successfully:', newScoreData.data);

      // OPTIMISTIC UPDATE: Immediately add the new score to the local state
      console.log('🔄 Adding score to local state optimistically...');
      setSelectedScorecardSections(prevSections => {
        if (!prevSections) return prevSections;
        
        return {
          ...prevSections,
          items: prevSections.items.map(s => {
            if (s.id === sectionId) {
              return {
                ...s,
                scores: {
                  ...s.scores,
                  items: [...(s.scores?.items || []), {
                    id: newScoreData.data.id,
                    name: newScoreData.data.name,
                    description: newScoreData.data.description || '',
                    key: newScoreData.data.key || '',
                    type: newScoreData.data.type,
                    order: newScoreData.data.order,
                    externalId: newScoreData.data.externalId
                  }]
                }
              };
            }
            return s;
          })
        };
      });
      
      // Select the newly created score
      console.log('🎯 Selecting newly created score');
      handleScoreSelect({
        ...newScoreData.data,
        sectionId: sectionId
      }, sectionId);
    } catch (error) {
      console.error('Error creating new score:', error);
    }
  };

  // Handle deleting a score
  const handleDeleteScore = async (scoreId: string) => {
    if (!selectedScorecard) {
      console.error('No selected scorecard for score deletion');
      return;
    }

    try {
      console.log('🗑️ Deleting score:', scoreId);
      
      // Delete the score from the database
      await amplifyClient.Score.delete({ id: scoreId });
      
      console.log('✅ Score deleted from database');
      
      // Close the score if it's currently selected
      if (selectedScore?.id === scoreId) {
        setSelectedScore(null);
        setMaximizedScoreId(null);
      }
      
      // OPTIMISTIC UPDATE: Immediately remove the score from local state
      console.log('🔄 Removing score from local state optimistically...');
      setSelectedScorecardSections(prevSections => {
        if (!prevSections) return prevSections;
        
        return {
          ...prevSections,
          items: prevSections.items.map(s => ({
            ...s,
            scores: {
              ...s.scores,
              items: (s.scores?.items || []).filter(score => score.id !== scoreId)
            }
          }))
        };
      });
      
      console.log('✅ Score removed from UI optimistically');
      
    } catch (error) {
      console.error('Error deleting score:', error);
      alert('Failed to delete score. Please try again.');
    }
  };

  // Handle closing the selected scorecard
  const handleCloseScorecard = () => {
    setSelectedScorecard(null);
    setSelectedScore(null);
    setIsFullWidth(false);
    setShouldExpandExamples(false); // Reset expand flag
    
    // Update URL without triggering a navigation/re-render
    window.history.pushState(null, '', '/lab/scorecards');
  };

  // Initial data load - optimized for immediate display
  const fetchScorecards = async () => {
    try {
      const accountResult = await amplifyClient.Account.list({
        filter: { key: { eq: ACCOUNT_KEY } }
      })

      if (accountResult.data.length === 0) {
        setIsLoading(false)
        return
      }

      const foundAccountId = accountResult.data[0].id
      setAccountId(foundAccountId)

      // Get scorecards as quickly as possible - no additional queries
      const initialScorecards = await amplifyClient.Scorecard.list({
        filter: { accountId: { eq: foundAccountId } }
      })

      // Debug: Log the first scorecard to check if guidelines are included
      if (initialScorecards.data.length > 0) {
        console.log('🔍 First scorecard data (checking for guidelines):', {
          id: initialScorecards.data[0].id,
          name: initialScorecards.data[0].name,
          guidelines: initialScorecards.data[0].guidelines,
          guidelinesType: typeof initialScorecards.data[0].guidelines,
          guidelinesLength: initialScorecards.data[0].guidelines?.length,
          hasGuidelines: 'guidelines' in initialScorecards.data[0],
          allFields: Object.keys(initialScorecards.data[0])
        });
      }

      // Immediately set scorecards with placeholder data to show them instantly
      const quickScorecards = initialScorecards.data
        .filter(s => s.accountId === foundAccountId)
        .map(scorecard => {
          console.log('🔍 Mapping scorecard:', {
            id: scorecard.id,
            name: scorecard.name,
            guidelines: scorecard.guidelines,
            hasGuidelines: 'guidelines' in scorecard
          });
          return {
            ...scorecard,
            examples: [] as string[],
            sections: async () => ({
              data: [],
              nextToken: null
            })
          } as Schema['Scorecard']['type'] & { examples: string[] };
        });

      // Show scorecards immediately without any loading states
      setScorecards(quickScorecards);
      setIsLoading(false);

      // Don't initialize score counts - let them be undefined until actually loaded
      // setScorecardScoreCounts will be updated progressively as data loads

      // Set loading states for progressive updates
      const loadingStates = quickScorecards.reduce((acc, scorecard) => ({
        ...acc,
        [scorecard.id]: true
      }), {} as Record<string, boolean>);
      setScorecardCountsLoading(loadingStates);

      // Start progressive loading in the background (non-blocking)
      console.log('🚀 Starting progressive loading for', quickScorecards.length, 'scorecards');
      setTimeout(() => {
        loadScoreCountsAndExamples(quickScorecards);
      }, 0);
      
      return quickScorecards;
    } catch (error) {
      console.error('Error fetching scorecards:', error)
      setError(error as Error)
      setIsLoading(false)
      return null;
    }
  }

  // Progressive loading of score counts and example items (optimized)
  const loadScoreCountsAndExamples = React.useCallback(async (scorecards: (Schema['Scorecard']['type'] & { examples: string[] })[]) => {
    console.log('🔄 loadScoreCountsAndExamples called with', scorecards.length, 'scorecards');
    
    // Process scorecards in small batches to avoid overwhelming the API
    const BATCH_SIZE = 3;
    const batches = [];
    for (let i = 0; i < scorecards.length; i += BATCH_SIZE) {
      batches.push(scorecards.slice(i, i + BATCH_SIZE));
    }
    console.log('📦 Created', batches.length, 'batches of scorecards');

    // Process batches with small delays to improve perceived performance
    for (const [batchIndex, batch] of batches.entries()) {
      // Add a small delay between batches to let the UI breathe
      if (batchIndex > 0) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }

      // Process all scorecards in this batch in parallel
      const batchPromises = batch.map(async (scorecard) => {
        try {
          console.log(`🔍 Processing scorecard: ${scorecard.name} (${scorecard.id})`);
          
          // Load sections directly from API (the scorecard.sections() method might not work on our placeholder objects)
          const sectionsResult = await amplifyClient.ScorecardSection.list({
            filter: { scorecardId: { eq: scorecard.id } }
          });
          const sections = sectionsResult.data || [];
          
          console.log(`📂 Found ${sections.length} sections for scorecard ${scorecard.name}`);
          
          if (sections.length === 0) {
            // No sections = no scores, update immediately
            console.log(`⚠️ No sections found for scorecard ${scorecard.name}, setting count to 0`);
            setScorecardScoreCounts(prev => ({ ...prev, [scorecard.id]: 0 }));
            setScorecardCountsLoading(prev => ({ ...prev, [scorecard.id]: false }));
            return;
          }

          // Load score counts for each section in parallel with timeout
          const sectionScorePromises = sections.map(async (section, index) => {
            try {
              console.log(`  📊 Loading scores for section ${index + 1}/${sections.length}: ${section.name} (${section.id})`);
              
              // Add timeout to prevent hanging requests
              const timeoutPromise = new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Timeout')), 10000)
              );
              const scoresPromise = fetchAllScoresForSection(section.id);
              
              const allScores = await Promise.race([scoresPromise, timeoutPromise]);
              const scoreCount = (allScores as any[]).length;
              console.log(`  ✅ Section ${section.name} has ${scoreCount} scores`);
              return scoreCount;
            } catch (error) {
              console.warn(`  ❌ Error loading scores for section ${section.id} (${section.name}):`, error);
              return 0;
            }
          });

          const sectionScoreCounts = await Promise.all(sectionScorePromises);
          const totalScoreCount = sectionScoreCounts.reduce((sum, count) => sum + count, 0);

          // Update score count immediately for this scorecard
          console.log(`✅ Loaded ${totalScoreCount} scores for scorecard ${scorecard.name} (${scorecard.id})`);
          setScorecardScoreCounts(prev => ({
            ...prev,
            [scorecard.id]: totalScoreCount
          }));

          setScorecardCountsLoading(prev => ({
            ...prev,
            [scorecard.id]: false
          }));

          // Load example items in the background (non-blocking)
          setTimeout(async () => {
            try {
              const associationsResult = await amplifyClient.ScorecardExampleItem.listByScorecard(scorecard.id);
              const exampleItems = associationsResult.data.map(association => `item:${association.itemId}`);

              // Only update if examples have changed to avoid unnecessary re-renders
              setScorecards(prevScorecards => 
                prevScorecards.map(sc => {
                  if (sc.id === scorecard.id) {
                    const currentExamples = (sc as any).examples || [];
                    if (JSON.stringify(currentExamples) !== JSON.stringify(exampleItems)) {
                      return {
                        ...sc,
                        examples: exampleItems,
                        sections: async () => ({ data: sections, nextToken: null })
                      } as Schema['Scorecard']['type'] & { examples: string[] };
                    }
                  }
                  return sc;
                })
              );
            } catch (error) {
              console.warn(`Error loading example items for scorecard ${scorecard.id}:`, error);
            }
          }, 50);

        } catch (error) {
          console.error(`Error loading data for scorecard ${scorecard.id}:`, error);
          // Show error state with 0 count
          setScorecardScoreCounts(prev => ({ ...prev, [scorecard.id]: 0 }));
          setScorecardCountsLoading(prev => ({ ...prev, [scorecard.id]: false }));
        }
      });

      // Wait for this batch to complete before moving to the next
      await Promise.allSettled(batchPromises);
    }
  }, [])

  useEffect(() => {
    fetchScorecards()
  }, [])

  // Removed redundant useEffect for loadScorecardSections - now handled in handleSelectScorecard

  // Helper function to fetch all scores for a section
  const fetchAllScoresForSection = async (sectionId: string) => {
    console.log('🔍 fetchAllScoresForSection called for sectionId:', sectionId);
    let allScores: Schema['Score']['type'][] = []
    let nextToken: string | null = null
    
    do {
      const scoresResult = await amplifyClient.Score.list({
        filter: { sectionId: { eq: sectionId } },
        ...(nextToken ? { nextToken } : {})
      })
      
      console.log('🔍 Scores result for section', sectionId, ':', scoresResult.data?.length, 'scores found');
      

      
      // Process scores to ensure complete data before adding to state
      // This helps React render name and description together
      const scoresWithDefaults = (scoresResult.data || []).map(score => {
        // Create complete score objects with all required fields
        return {
          ...score,
          name: score.name || 'Unnamed Score',
          description: score.description || '',
          key: score.key || '',
          type: score.type || 'Score'
        };
      });
      
      allScores = [...allScores, ...scoresWithDefaults]
      nextToken = scoresResult.nextToken
    } while (nextToken)
    
    console.log('🔍 Final scores for section', sectionId, ':', allScores.map(s => ({id: s.id, name: s.name})));
    return allScores
  }

  // Removed fetchSectionsWithScores - functionality moved to handleSelectScorecard

  // Handle creating a new scorecard
  const handleCreate = async () => {
    if (!accountId) {
      console.error('No accountId available for scorecard creation');
      return;
    }

    try {
      const createData = {
        name: 'New Scorecard',
        key: `scorecard_${Date.now()}`, // Generate a unique key
        accountId
      };
      console.log('Creating scorecard with data:', createData);

      // Create a new scorecard in the database first
      const newScorecardData = await amplifyClient.Scorecard.create(createData);

      console.log('Scorecard creation response:', newScorecardData);
      console.log('Response data:', newScorecardData?.data);

      if (!newScorecardData.data) {
        console.error('Failed to create scorecard - no data returned');
        console.error('Full response object:', JSON.stringify(newScorecardData, null, 2));
        return;
      }

      // Refresh the scorecards list to include the new one
      await fetchScorecards();

      // Select the newly created scorecard
      handleSelectScorecard(newScorecardData.data);
      setSelectedScorecardSections({ items: [] });
    } catch (error) {
      console.error('Error creating new scorecard:', error);
      console.error('Error details:', {
        message: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : 'No stack trace',
        fullError: error
      });
    }
  }

  // Handle editing an existing scorecard
  const handleEdit = async (scorecard: Schema['Scorecard']['type']) => {
    try {
      const fullScorecard = await amplifyClient.Scorecard.get({ id: scorecard.id })

      const scorecardData = fullScorecard.data
      if (!scorecardData) {
        setError(new Error(`Could not find scorecard with ID ${scorecard.id}`))
        return
      }

      // Debug: Log scorecard data to check if guidelines are included
      console.log('🔍 Full scorecard data (checking for guidelines):', {
        id: scorecardData.id,
        name: scorecardData.name,
        guidelines: scorecardData.guidelines,
        hasGuidelines: 'guidelines' in scorecardData,
        allFields: Object.keys(scorecardData)
      });

      // Get all sections for this scorecard
      const sectionsResult = await amplifyClient.ScorecardSection.list({
        filter: { scorecardId: { eq: scorecard.id } }
      })
      
      const sortedSections = sectionsResult.data.sort((a, b) => a.order - b.order)

      // Get scores for each section
      const sectionsWithScores = await Promise.all(sortedSections.map(async section => {
        const allScores = await fetchAllScoresForSection(section.id)
        return {
          ...section,
          scores: async () => ({
            data: allScores.sort((a, b) => a.order - b.order),
            nextToken: null
          })
        }
      }))

      const accountResult = await amplifyClient.Account.get({ 
        id: scorecardData.accountId 
      })
      if (!accountResult.data) {
        throw new Error('Account not found')
      }

      const fullScorecardData = {
        ...scorecardData,
        account: async () => amplifyClient.Account.get({ id: scorecardData.accountId }),
        sections: async () => ({
          data: sectionsWithScores,
          nextToken: null
        }),
        evaluations: async () => amplifyClient.Evaluation.list({
          filter: { scorecardId: { eq: scorecardData.id } }
        }),
        batchJobs: async () => amplifyClient.BatchJob.list({
          filter: { scorecardId: { eq: scorecardData.id } }
        }),
        item: async () => Promise.resolve({ data: null }),
        scoringJobs: async () => amplifyClient.ScoringJob.list({
          filter: { scorecardId: { eq: scorecardData.id } }
        }),
        scoreResults: async () => amplifyClient.ScoreResult.list({
          filter: { scorecardId: { eq: scorecardData.id } }
        }),
        actions: [],
        tasks: async (): Promise<AmplifyListResult<Schema['Task']['type']>> => {
          return listFromModel<Schema['Task']['type']>(
            client.models.Task,
            { scorecardId: { eq: scorecardData.id } }
          );
        }
      } as Schema['Scorecard']['type']
      
      handleSelectScorecard(fullScorecardData);
    } catch (error) {
      console.error('Error editing scorecard:', error)
      setError(error as Error)
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
      
      setLeftPanelWidth(newWidth);
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
  }

  // Add back the renderSelectedScorecard function
  const renderSelectedScorecard = () => {
    if (!selectedScorecard || !selectedScorecardSections) return null;

    const scorecardData = {
      id: selectedScorecard.id,
      name: selectedScorecard.name,
      key: selectedScorecard.key || '',
      description: selectedScorecard.description || '',
      guidelines: selectedScorecard.guidelines || '',
      type: 'scorecard',
      configuration: {},
      order: 0,
      externalId: selectedScorecard.externalId || '',
      sections: selectedScorecardSections || { items: [] },
      // Combine existing examples with newly created ones
      examples: [...(scorecardExamples || [])]
    }

    // Debug: Log what we're passing to ScorecardComponent
    console.log('🔍 scorecardData being passed to ScorecardComponent:', {
      id: scorecardData.id,
      name: scorecardData.name,
      guidelines: scorecardData.guidelines,
      guidelinesLength: scorecardData.guidelines?.length,
      hasGuidelines: 'guidelines' in scorecardData
    });

    // Check if we're in scorecard + task two-column layout
    const isInScorecardTaskLayout = selectedScorecard && selectedTask && !selectedScore;

    return (
      <div className={cn(
        "h-full overflow-y-auto overflow-x-hidden",
        maximizedScoreId ? "hidden" : ""
      )}
      style={!maximizedScoreId && !isInScorecardTaskLayout && (selectedScore || selectedItem || selectedTask) ? {
        width: `${scorecardDetailWidth}%`
      } : { width: '100%' }}>
        <ScorecardComponent
          variant="detail"
          score={scorecardData}
          onEdit={() => handleEdit(selectedScorecard)}
          onViewData={() => {
            console.log('View data for scorecard:', selectedScorecard.id)
            // TODO: Implement data source view
          }}
          onFeedbackAnalysis={() => handleScorecardFeedbackAnalysis(selectedScorecard.id)}
          onCostAnalysis={() => handleScorecardCostAnalysis(selectedScorecard.id)}
          isFullWidth={isFullWidth}
          onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
          onClose={handleCloseScorecard}
          onSave={async () => {
            console.log('🔄 onSave called - refreshing scorecards and updating selectedScorecard...');
            const refreshedScorecards = await fetchScorecards();
            
            // Update selectedScorecard with fresh data from the API
            if (selectedScorecard && refreshedScorecards) {
              const updatedScorecard = refreshedScorecards.find(sc => sc.id === selectedScorecard.id);
              if (updatedScorecard) {
                console.log('🔄 Updating selectedScorecard with fresh guidelines:', {
                  oldGuidelines: selectedScorecard.guidelines,
                  newGuidelines: updatedScorecard.guidelines
                });
                setSelectedScorecard(updatedScorecard);
              }
            }
          }}
          onScoreSelect={handleScoreSelect}
          selectedScoreId={selectedScore?.id}
          onCreateItem={(initialContent) => {
            // Pass a callback that will update the scorecard when item is saved
            handleCreateItem(initialContent);
          }}
          onEditItem={handleEditItem}
          shouldExpandExamples={shouldExpandExamples}
          onExamplesExpanded={() => setShouldExpandExamples(false)}
          onTaskCreated={handleTaskCreated}
          onCreateScore={handleCreateScore}
        />
      </div>
    );
  };

  // Memoize the processed score data to ensure stable rendering
  const processedScore = React.useMemo(() => {
    if (!selectedScore) return null;
    
    console.log('Processing score data for ScoreComponent:', selectedScore);
    
    // Pre-process the score data to ensure name and description render together
    const processed = {
      id: selectedScore.id,
      name: selectedScore.name,
      description: selectedScore.description || '',
      type: selectedScore.type,
      order: selectedScore.order,
      key: selectedScore.key || '',
      externalId: selectedScore.externalId || ''
    };
    
    console.log('Processed score data:', processed);
    return processed;
  }, [selectedScore]);

  // Add back the renderSelectedScore function
  const renderSelectedScore = () => {
    if (!selectedScore || !processedScore) return null;

    return (
      <div className="h-full overflow-y-auto overflow-x-hidden w-full">
        <ScoreComponent
          score={processedScore}
          variant="detail"
          isFullWidth={maximizedScoreId === selectedScore.id}
          onToggleFullWidth={() => setMaximizedScoreId(maximizedScoreId ? null : selectedScore.id)}
          onClose={() => {
            setSelectedScore(null);
            setSelectedVersionId(null);
            setMaximizedScoreId(null);
            // If there's a task open when closing score, also close the task
            if (selectedTask) {
              setSelectedTask(null);
              setIsTaskViewActive(false);
            }
            // If there's feedback analysis open when closing score, also close it
            if (feedbackAnalysisPanel?.isOpen) {
              setFeedbackAnalysisPanel(null);
            }
          }}
          onDelete={() => handleDeleteScore(selectedScore.id)}
          initialSelectedVersionId={selectedVersionId}
          onVersionSelect={handleVersionSelect}
          onSave={async () => {
            // Refresh the scorecard data to get updated score information
            await fetchScorecards();
            
            // Also reload the scorecard sections to get updated score data
            if (selectedScorecard) {
              console.log('🔄 Reloading scorecard sections after save...');
              try {
                // Use GraphQL query to fetch sections for this scorecard
                const sectionsResult = await amplifyClient.ScorecardSection.list({
                  filter: { scorecardId: { eq: selectedScorecard.id } }
                });
                const sections = sectionsResult.data || [];
                
                // Fetch ALL score data in parallel before setting state
                const transformedSections = {
                  items: await Promise.all(sections.map(async section => {
                    const allScores = await fetchAllScoresForSection(section.id);
                    
                    return {
                      id: section.id,
                      name: section.name,
                      order: section.order,
                      scores: {
                        items: allScores.map(score => ({
                          id: score.id,
                          name: score.name,
                          key: score.key || '',
                          description: score.description || '',
                          order: score.order,
                          type: score.type,
                          externalId: score.externalId,
                        }))
                      }
                    }
                  }))
                };
                
                // Set all sections with complete score data at once
                setSelectedScorecardSections(transformedSections);
                
                // Update the selectedScore state with the fresh data
                if (selectedScore) {
                  for (const section of transformedSections.items) {
                    const updatedScore = section.scores.items.find(s => s.id === selectedScore.id);
                    if (updatedScore) {
                      setSelectedScore({...updatedScore, sectionId: section.id});
                      console.log('✅ Updated selectedScore with fresh data:', updatedScore.name);
                      break;
                    }
                  }
                }
              } catch (error) {
                console.error('Error reloading scorecard sections:', error);
              }
            }
          }}
          onFeedbackAnalysis={() => handleScoreFeedbackAnalysis(selectedScore.id, selectedScore.name, selectedScorecard?.id)}
          onCostAnalysis={() => handleScoreCostAnalysis(selectedScore.id, selectedScorecard?.id)}
          exampleItems={scorecardExamples.map(example => {
            // Extract item ID from "item:uuid" format
            const itemId = example.replace('item:', '');
            return {
              id: itemId,
              displayValue: `Item ${itemId.slice(0, 8)}...` // Show first 8 chars of ID as display
            };
          })}
          scorecardName={selectedScorecard?.name}
          onTaskCreated={handleTaskCreated}
        />
      </div>
    );
  };

  // Add renderSelectedTask function
  const renderSelectedTask = () => {
    if (!selectedTask) return null;

    // When in score + task layout, task component takes full width of its container
    const isInScoreTaskLayout = selectedScore && selectedTask;
    // When in scorecard + task layout, task component also takes full width of its container
    const isInScorecardTaskLayout = selectedScorecard && selectedTask && !selectedScore;

    // Debug: Log the task stages to see what we're passing
    console.log('Rendering task with stages:', {
      taskId: selectedTask.id,
      stages: selectedTask.stages,
      currentStageName: selectedTask.currentStageName,
      stagesCount: selectedTask.stages?.length || 0
    });

    const taskData = {
      id: selectedTask.id,
      type: selectedTask.type || 'Task',
      name: selectedTask.name,  
      description: selectedTask.description,
      scorecard: selectedScorecard?.name || 'Unknown Scorecard',
      score: selectedScore?.name || 'Unknown Score',
      time: selectedTask.createdAt || new Date().toISOString(),
      command: selectedTask.command,
      output: selectedTask.output,
      attachedFiles: selectedTask.attachedFiles,
      stdout: selectedTask.stdout,
      stderr: selectedTask.stderr,
      stages: selectedTask.stages,
      currentStageName: selectedTask.currentStageName,
      processedItems: selectedTask.processedItems,
      totalItems: selectedTask.totalItems,
      startedAt: selectedTask.startedAt,
      estimatedCompletionAt: selectedTask.estimatedCompletionAt,
      status: selectedTask.status,
      dispatchStatus: selectedTask.dispatchStatus,
      celeryTaskId: selectedTask.celeryTaskId,
      workerNodeId: selectedTask.workerNodeId,
      completedAt: selectedTask.completedAt,
      errorMessage: selectedTask.errorMessage
    };

    return (
      <div className={cn(
        "h-full overflow-y-auto overflow-x-hidden",
        (isInScoreTaskLayout || isInScorecardTaskLayout) ? "w-full" : ""
      )}
      style={!(isInScoreTaskLayout || isInScorecardTaskLayout) ? {
        width: `${100 - scorecardDetailWidth}%`
      } : undefined}>
        <Task
          variant="detail"
          task={taskData}
          onClose={handleCloseTask}
          showProgress={true}
          renderHeader={(props) => <TaskHeader {...props} />}
          renderContent={(props) => <TaskContent {...props} />}
        />
      </div>
    );
  };

  // Add renderSelectedItem function
  const renderSelectedItem = () => {
    if (!selectedItem) return null;

    return (
      <div className={cn(
        "h-full overflow-y-auto overflow-x-hidden"
      )}
      style={{
        width: `${100 - scorecardDetailWidth}%`
      }}>
        <ItemComponent
          item={selectedItem}
          variant="detail"
          onSave={async (item) => {
            const success = await handleSaveItem(item);
            if (success && isCreatingItem) {
              // Close the item view after successful creation and show a helpful message
              setTimeout(() => {
                setSelectedItem(null);
                setIsCreatingItem(false);
                // You can expand the examples section here if needed
              }, 1500); // Give user time to see the success message
            }
          }}
          onClose={() => {
            setSelectedItem(null);
            setIsCreatingItem(false);
          }}
        />
      </div>
    );
  };

  if (error) {
    return (
      <div className="p-4">
        <div className="text-red-500 mb-2">
          Error loading scorecards: {error.message}
        </div>
      </div>
    )
  }

  if (isLoading) {
    return <ScorecardDashboardSkeleton />
  }

  return (
    <div className="@container flex flex-col h-full p-3 overflow-hidden">
      <div className="flex flex-1 min-h-0">
        {/* Grid Panel */}
        <motion.div 
          className={cn(
            "h-full overflow-auto",
            selectedScore || (selectedScorecard && isFullWidth) || (selectedScorecard && selectedTask) || feedbackAnalysisPanel?.isOpen ? "hidden" : selectedScorecard ? "flex" : "w-full"
          )}
          animate={{
            width: selectedScorecard && !isFullWidth && !selectedTask && !feedbackAnalysisPanel?.isOpen 
              ? `${leftPanelWidth}%`
              : selectedScore || (selectedScorecard && isFullWidth) || (selectedScorecard && selectedTask) || feedbackAnalysisPanel?.isOpen 
                ? '0%'
                : '100%'
          }}
          transition={{
            type: 'spring',
            stiffness: 300,
            damping: 30
          }}
        >
          <div className="space-y-3 w-full">
            <div className="flex justify-end">
              <Button 
                onClick={handleCreate} 
                variant="ghost" 
                className="bg-card hover:bg-accent text-muted-foreground"
              >
                New Scorecard
              </Button>
            </div>
            <div className="@container">
              <ScorecardGrid 
                scorecards={scorecards as (Schema['Scorecard']['type'] & { examples: string[] })[]}
                scorecardScoreCounts={scorecardScoreCounts}
                scorecardCountsLoading={scorecardCountsLoading}
                selectedScorecardId={selectedScorecard?.id}
                onSelectScorecard={handleSelectScorecard}
                onEdit={handleEdit}
                onFeedbackAnalysis={handleScorecardFeedbackAnalysis}
                onCostAnalysis={handleScorecardCostAnalysis}
                scorecardRefsMap={scorecardRefsMap}
              />
            </div>
          </div>
        </motion.div>

        {/* Resize Handle between Grid and Detail */}
        {selectedScorecard && !isFullWidth && !selectedScore && !selectedTask && !feedbackAnalysisPanel?.isOpen && (
          <div
            className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
            onMouseDown={handleDragStart}
          >
            <div className="absolute inset-0 rounded-full transition-colors duration-150 
              group-hover:bg-accent" />
          </div>
        )}

        {/* Detail Panel Container */}
        <div className="flex-1 flex overflow-hidden">
          {/* When we have a selected score and feedback analysis, show score + feedback layout */}
          <AnimatePresence mode="wait">
            {selectedScore && (feedbackAnalysisPanel?.isOpen || costAnalysisPanel?.isOpen) ? (
              <motion.div
                key="score-analysis-layout"
                initial={{ opacity: 0, x: '100%' }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: '100%' }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                className="flex flex-1 overflow-hidden"
              >
                {/* Score Component (Left Column) - Explicitly set to 50% */}
                <div className="w-1/2 overflow-hidden flex-shrink-0">
                  {renderSelectedScore()}
                </div>
                
                {/* Gap between columns with drag handler */}
                <motion.div 
                  className="w-3 flex-shrink-0 relative cursor-col-resize group"
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: 12 }}
                  transition={{ duration: 0.3 }}
                  onMouseDown={(e: React.MouseEvent) => {
                    e.preventDefault();
                    const startX = e.clientX;
                    const startWidth = 50; // Start from 50% split
                    const container = e.currentTarget.parentElement;
                    if (!container) return;
                    
                    const handleDrag = (e: MouseEvent) => {
                      const deltaX = e.clientX - startX;
                      const containerWidth = container.getBoundingClientRect().width;
                      const deltaPercentage = (deltaX / containerWidth) * 100;
                      const newLeftWidth = Math.min(Math.max(startWidth + deltaPercentage, 25), 75);
                      
                      // Update both panels dynamically
                      const leftPanel = container.children[0] as HTMLElement;
                      const rightPanel = container.children[2] as HTMLElement;
                      if (leftPanel && rightPanel) {
                        leftPanel.style.width = `${newLeftWidth}%`;
                        rightPanel.style.width = `${100 - newLeftWidth}%`;
                      }
                    };
                    
                    const handleDragEnd = () => {
                      document.removeEventListener('mousemove', handleDrag);
                      document.removeEventListener('mouseup', handleDragEnd);
                      document.body.style.cursor = '';
                    };
                    
                    document.body.style.cursor = 'col-resize';
                    document.addEventListener('mousemove', handleDrag);
                    document.addEventListener('mouseup', handleDragEnd);
                  }}
                >
                  <div className="absolute inset-0 rounded-full transition-colors duration-150 
                    group-hover:bg-accent" />
                </motion.div>
                
                {/* Analysis Panel (Right Column) - Take remaining space */}
                <div className="flex-1 overflow-hidden">
                <div className="h-full overflow-y-auto overflow-x-hidden w-full rounded-lg text-card-foreground hover:bg-accent/50 transition-colors bg-card-selected flex flex-col">
                  <div className="p-4 w-full flex-1 flex flex-col min-h-0">
                    <div className="w-full h-full flex flex-col min-h-0">
                      <div className="flex justify-between items-center mb-4 flex-shrink-0">
                        <div className="flex items-center gap-2">
                          {feedbackAnalysisPanel?.isOpen ? (
                            <MessageCircleMore className="h-5 w-5 text-foreground" />
                          ) : (
                            <Coins className="h-5 w-5 text-foreground" />
                          )}
                          <h2 className="text-lg font-semibold">{feedbackAnalysisPanel?.isOpen ? 'Feedback Analysis' : 'Cost Analysis'}</h2>
                        </div>
                        <CardButton
                          icon={X}
                          onClick={() => { setFeedbackAnalysisPanel(null); setCostAnalysisPanel(null); }}
                          aria-label="Close analysis"
                        />
                      </div>
                      <div className="flex-1 overflow-y-auto min-h-0">
                        {feedbackAnalysisPanel?.isOpen ? (
                          <AdHocFeedbackAnalysis
                            scorecardId={feedbackAnalysisPanel.scorecardId}
                            scoreId={feedbackAnalysisPanel.scoreId}
                            scoreName={feedbackAnalysisPanel.scoreName}
                            showHeader={false}
                            showConfiguration={true}
                            defaultDays={7}
                          />
                        ) : (
                          <AdHocCostAnalysis
                            scorecardId={costAnalysisPanel?.type === 'scorecard' ? costAnalysisPanel?.scorecardId : undefined}
                            scoreId={costAnalysisPanel?.type === 'score' ? costAnalysisPanel?.scoreId : undefined}
                            defaultHours={24}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                </div>
              </motion.div>
            ) : selectedScorecard && (feedbackAnalysisPanel?.isOpen || costAnalysisPanel?.isOpen) && !selectedScore ? (
              <motion.div
                key="scorecard-analysis-layout"
                initial={{ opacity: 0, x: '100%' }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: '100%' }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                className="flex flex-1 overflow-hidden"
              >
                {/* Scorecard + Feedback Analysis Layout: Scorecard (Left Column) - Explicitly set to 50% */}
                <div className="w-1/2 overflow-hidden flex-shrink-0">
                  {renderSelectedScorecard()}
                </div>
                
                {/* Gap between columns with drag handler */}
                <motion.div 
                  className="w-3 flex-shrink-0 relative cursor-col-resize group"
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: 12 }}
                  transition={{ duration: 0.3 }}
                  onMouseDown={(e: React.MouseEvent) => {
                    e.preventDefault();
                    const startX = e.clientX;
                    const startWidth = 50; // Start from 50% split
                    const container = e.currentTarget.parentElement;
                    if (!container) return;
                    
                    const handleDrag = (e: MouseEvent) => {
                      const deltaX = e.clientX - startX;
                      const containerWidth = container.getBoundingClientRect().width;
                      const deltaPercentage = (deltaX / containerWidth) * 100;
                      const newLeftWidth = Math.min(Math.max(startWidth + deltaPercentage, 25), 75);
                      
                      // Update both panels dynamically
                      const leftPanel = container.children[0] as HTMLElement;
                      const rightPanel = container.children[2] as HTMLElement;
                      if (leftPanel && rightPanel) {
                        leftPanel.style.width = `${newLeftWidth}%`;
                        rightPanel.style.width = `${100 - newLeftWidth}%`;
                      }
                    };
                    
                    const handleDragEnd = () => {
                      document.removeEventListener('mousemove', handleDrag);
                      document.removeEventListener('mouseup', handleDragEnd);
                      document.body.style.cursor = '';
                    };
                    
                    document.body.style.cursor = 'col-resize';
                    document.addEventListener('mousemove', handleDrag);
                    document.addEventListener('mouseup', handleDragEnd);
                  }}
                >
                  <div className="absolute inset-0 rounded-full transition-colors duration-150 
                    group-hover:bg-accent" />
                </motion.div>
                
                {/* Analysis Panel (Right Column) - Take remaining space */}
                <div className="flex-1 overflow-hidden">
                <div className="h-full overflow-y-auto overflow-x-hidden w-full rounded-lg text-card-foreground hover:bg-accent/50 transition-colors bg-card-selected flex flex-col">
                  <div className="p-4 w-full flex-1 flex flex-col min-h-0">
                    <div className="w-full h-full flex flex-col min-h-0">
                      <div className="flex justify-between items-center mb-4 flex-shrink-0">
                        <div className="flex items-center gap-2">
                          {feedbackAnalysisPanel?.isOpen ? (
                            <MessageCircleMore className="h-5 w-5 text-foreground" />
                          ) : (
                            <Coins className="h-5 w-5 text-foreground" />
                          )}
                          <h2 className="text-lg font-semibold">{feedbackAnalysisPanel?.isOpen ? 'Feedback Analysis' : 'Cost Analysis'}</h2>
                        </div>
                        <CardButton
                          icon={X}
                          onClick={() => { setFeedbackAnalysisPanel(null); setCostAnalysisPanel(null); }}
                          aria-label="Close analysis"
                        />
                      </div>
                      <div className="flex-1 overflow-y-auto min-h-0">
                        {feedbackAnalysisPanel?.isOpen ? (
                          <AdHocFeedbackAnalysis
                            scorecardId={feedbackAnalysisPanel.scorecardId}
                            scoreId={feedbackAnalysisPanel.scoreId}
                            showHeader={false}
                            showConfiguration={true}
                            defaultDays={7}
                          />
                        ) : (
                          <AdHocCostAnalysis
                            scorecardId={costAnalysisPanel?.type === 'scorecard' ? costAnalysisPanel?.scorecardId : undefined}
                            scoreId={costAnalysisPanel?.type === 'score' ? costAnalysisPanel?.scoreId : undefined}
                            defaultHours={24}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                </div>
              </motion.div>
            ) : selectedScore && selectedTask ? (
            <>
              {/* Score Component (Left Column) */}
              <div className="flex-1 overflow-hidden">
                {renderSelectedScore()}
              </div>
              
              {/* Gap between columns */}
              <div className="w-3 flex-shrink-0" />
              
              {/* Task Component (Right Column) */}
              <div className="flex-1 overflow-hidden">
                {renderSelectedTask()}
              </div>
            </>
          ) : selectedScorecard && selectedTask && !selectedScore ? (
            <>
              {/* Scorecard + Task Layout: Scorecard (Left Column) */}
              <div className="flex-1 overflow-hidden">
                {renderSelectedScorecard()}
              </div>
              
              {/* Gap between columns */}
              <div className="w-3 flex-shrink-0" />
              
              {/* Task Component (Right Column) */}
              <div className="flex-1 overflow-hidden">
                {renderSelectedTask()}
              </div>
            </>
          ) : (
            <>
              {/* Default layout: Scorecard + (Score/Item/Task) */}
              {renderSelectedScorecard()}
              
              {/* Resize Handle between Scorecard and Score/Item/Task */}
              {(selectedScore || selectedItem || selectedTask) && !maximizedScoreId && (
                <div
                  className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
                  onMouseDown={(e: React.MouseEvent<HTMLDivElement>) => {
                    e.preventDefault()
                    const startX = e.pageX
                    const startDetailWidth = scorecardDetailWidth
                    const container = e.currentTarget.parentElement
                    if (!container) return

                    const handleDrag = (e: MouseEvent) => {
                      const deltaX = e.pageX - startX
                      const containerWidth = container.getBoundingClientRect().width
                      const deltaPercent = (deltaX / containerWidth) * 100
                      const newDetailWidth = Math.min(Math.max(startDetailWidth + deltaPercent, 20), 80)
                      requestAnimationFrame(() => {
                        setScorecardDetailWidth(newDetailWidth)
                      })
                    }

                    const handleDragEnd = () => {
                      document.removeEventListener('mousemove', handleDrag)
                      document.removeEventListener('mouseup', handleDragEnd)
                      document.body.style.cursor = ''
                    }

                    document.body.style.cursor = 'col-resize'
                    document.addEventListener('mousemove', handleDrag)
                    document.addEventListener('mouseup', handleDragEnd)
                  }}
                >
                  <div className="absolute inset-0 rounded-full transition-colors duration-150 
                    group-hover:bg-accent" />
                </div>
              )}
              
              {/* Only render these when not in two-column layout */}
              {!selectedTask && !feedbackAnalysisPanel?.isOpen && renderSelectedScore()}
              {!selectedTask && !feedbackAnalysisPanel?.isOpen && renderSelectedItem()}
              {!selectedScore && !selectedScorecard && renderSelectedTask()}
            </>
          )}
          </AnimatePresence>
        </div>
      </div>

    </div>
  )
}


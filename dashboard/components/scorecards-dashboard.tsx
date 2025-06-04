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
  X
} from "lucide-react"
import { ScoreCount } from "./scorecards/score-count"
import { CardButton } from "./CardButton"
import { DatasetConfigFormComponent } from "./dataset-config-form"
import { listFromModel } from "@/utils/amplify-helpers"
import { AmplifyListResult } from '@/types/shared'
import { graphqlRequest } from "@/utils/amplify-client"
import { generateClient } from "aws-amplify/data"
import ScorecardComponent from "./scorecards/ScorecardComponent"
import { cn } from "@/lib/utils"
import { ScoreComponent } from "./ui/score-component"
import { ItemComponent, type ItemData } from "./ui/item-component"
import ScorecardDetailView from "./scorecards/ScorecardDetailView"
import { useRouter, usePathname, useParams } from "next/navigation"
import { ScorecardDashboardSkeleton } from "./loading-skeleton"

const ACCOUNT_KEY = 'call-criteria'

export default function ScorecardsComponent({
  initialSelectedScorecardId = null,
  initialSelectedScoreId = null
}: {
  initialSelectedScorecardId?: string | null,
  initialSelectedScoreId?: string | null
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
  } | null>(null)
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
  const [showDatasetConfig, setShowDatasetConfig] = useState(false)
  const [selectedScorecardForDataset, setSelectedScorecardForDataset] = useState<string>("")
  const [leftPanelWidth, setLeftPanelWidth] = useState(40)
  const [scorecardScoreCounts, setScorecardScoreCounts] = useState<Record<string, number>>({})
  const [scorecardDetailWidth, setScorecardDetailWidth] = useState(50)
  const [maximizedScoreId, setMaximizedScoreId] = useState<string | null>(null)
  const [selectedItem, setSelectedItem] = useState<any | null>(null)
  const [isCreatingItem, setIsCreatingItem] = useState(false)
  const [scorecardExamples, setScorecardExamples] = useState<string[]>([])
  const [shouldExpandExamples, setShouldExpandExamples] = useState(false)
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
          handleScoreSelect({...score, sectionId: section.id}, section.id);
          break;
        }
      }
    }
  }, [initialSelectedScoreId, selectedScorecardSections]);

  // Handle browser back/forward navigation with popstate event
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      // Extract scorecard ID from URL if present
      const scorecardMatch = window.location.pathname.match(/\/lab\/scorecards\/([^\/]+)(?:\/|$)/);
      const scorecardIdFromUrl = scorecardMatch ? scorecardMatch[1] : null;
      
      // Extract score ID from URL if present
      const scoreMatch = window.location.pathname.match(/\/lab\/scorecards\/[^\/]+\/scores\/([^\/]+)$/);
      const scoreIdFromUrl = scoreMatch ? scoreMatch[1] : null;
      
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
                break;
              }
            }
          } else {
            setSelectedScore(null);
          }
        }
      } else {
        setSelectedScorecard(null);
        setSelectedScore(null);
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
      
      setSelectedScorecard(scorecard);
      // Conditionally reset selected score:
      // If we are changing to a different scorecard OR if no initialSelectedScoreId is actively being processed
      // (This check might need refinement based on when initialSelectedScoreId is cleared or considered 'processed')
      if (selectedScorecard?.id !== scorecard?.id || !initialSelectedScoreId) {
          setSelectedScore(null);
      }
      
      // Reset scorecard examples for the new scorecard
      setScorecardExamples([]);
      setShouldExpandExamples(false); // Reset expand flag
      
      // Conditionally update URL:
      // If we are selecting a scorecard AND there isn't an initialSelectedScoreId that matches the current scorecard context,
      // then update the URL to the scorecard. Otherwise, let the score selection logic handle the final URL.
      // This logic assumes initialSelectedScoreId is available in this component's scope.
      if (scorecard && (!initialSelectedScoreId || initialSelectedScorecardId !== scorecard.id)) {
        const newPathname = `/lab/scorecards/${scorecard.id}`;
        window.history.pushState(null, '', newPathname);
      } else if (!scorecard) { // Clearing scorecard selection
        window.history.pushState(null, '', '/lab/scorecards');
      }
      
      // Scroll to the selected scorecard after a brief delay to allow layout updates
      if (scorecard) {
        setTimeout(() => {
          scrollToSelectedScorecard(scorecard.id);
        }, 100);
      }
      
      if (scorecard && isNarrowViewport) {
        setIsFullWidth(true);
      }
      
      // Load sections and example items for the selected scorecard and wait for all data before setting state
      if (scorecard) {
        console.log('🔵 Loading data for scorecard:', {
          scorecardId: scorecard.id,
          scorecardName: scorecard.name
        });
        try {
          console.log('🟡 Getting full scorecard object with all relationships...');
          
          // Get the full scorecard object from the API with all its relationship methods
          const fullScorecard = await amplifyClient.Scorecard.get({ id: scorecard.id });
          const fullScorecardData = fullScorecard.data;
          
          if (!fullScorecardData) {
            throw new Error(`Could not find scorecard with ID ${scorecard.id}`);
          }
          
          console.log('🟡 Full scorecard object inspection:', {
            scorecardId: fullScorecardData.id,
            scorecardName: fullScorecardData.name,
            hasExampleItemsProperty: 'exampleItems' in fullScorecardData,
            allMethods: Object.getOwnPropertyNames(fullScorecardData).filter(prop => {
              try {
                return typeof (fullScorecardData as any)[prop] === 'function';
              } catch {
                return false;
              }
            })
          });
          
          // Load sections first
          console.log('🟡 Loading sections...');
          const sectionsResult = await fullScorecardData.sections();
          const sections = sectionsResult.data || [];
          
          // Load items associated with this scorecard via the ScorecardExampleItem join table
          console.log('🟡 Loading example items using ScorecardExampleItem join table...');
          let exampleItems: any[] = [];
          
          try {
            // Query the ScorecardExampleItem join table to get associated items
            const itemAssociationsResult = await graphqlRequest<{
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
            `, { scorecardId: fullScorecardData.id });
            
            // Extract the actual items from the associations and sort by updatedAt
            exampleItems = (itemAssociationsResult.data?.listScorecardExampleItemByScorecardId?.items || [])
              .map(association => association.item)
              .filter(item => item !== null) // Filter out any null items
              .sort((a, b) => {
                const dateA = new Date(a.updatedAt || a.createdAt || '').getTime();
                const dateB = new Date(b.updatedAt || b.createdAt || '').getTime();
                return dateB - dateA; // DESC order (newest first)
              });
              
            console.log('🟡 Items loaded via ScorecardExampleItem join table:', {
              itemCount: exampleItems.length,
              items: exampleItems
            });
          } catch (error) {
            console.error('🔴 Error loading items via ScorecardExampleItem join table:', error);
          }
          
          console.log('🟢 Data loaded successfully:', {
            scorecardId: fullScorecardData.id,
            scorecardName: fullScorecardData.name,
            sectionsCount: sections.length,
            exampleItemsCount: exampleItems.length,
            exampleItemsDetails: exampleItems.map(item => ({
              id: item?.id,
              externalId: item?.externalId,
              description: item?.description,
              scorecardId: item?.scorecardId
            }))
          });
          
          // Set the example items in the format expected by the component
          const exampleItemsFormatted = exampleItems.map(item => `item:${item.id}`);
          setScorecardExamples(exampleItemsFormatted);
          
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
                  }))
                }
              }
            }))
          };
          
          // Set all sections with complete score data at once
          setSelectedScorecardSections(transformedSections);
        } catch (error) {
          console.error('Error loading scorecard sections and example items:', error);
          setError(error as Error);
        }
      } else {
        setSelectedScorecardSections(null);
      }
    }
  };

  // Custom setter for selectedScore that handles both state and URL
  const handleScoreSelect = (score: any, sectionId: string) => {
    // Only update state if the selected score has changed
    if (score?.id !== selectedScore?.id) {
      setSelectedScore({...score, sectionId});
      // Reset item selection when selecting a score
      setSelectedItem(null);
      setIsCreatingItem(false);
      
      // Update URL without triggering a navigation/re-render
      if (selectedScorecard) {
        const newPathname = `/lab/scorecards/${selectedScorecard.id}/scores/${score.id}`;
        window.history.pushState(null, '', newPathname);
      }
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
        } = {
          accountId: item.accountId || accountId!,
          isEvaluation: item.isEvaluation || false
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

  // Handle closing the selected scorecard
  const handleCloseScorecard = () => {
    setSelectedScorecard(null);
    setSelectedScore(null);
    setIsFullWidth(false);
    setShouldExpandExamples(false); // Reset expand flag
    
    // Update URL without triggering a navigation/re-render
    window.history.pushState(null, '', '/lab/scorecards');
  };

  // Initial data load
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

      type NestedScorecard = Schema['Scorecard']['type'] & {
        sections?: {
          data?: Array<{
            id: string;
            scores?: {
              data?: Array<{ id: string }>;
            };
          }>;
        };
      }

      // Get scorecards with nested sections and scores
      const initialScorecards = await amplifyClient.Scorecard.list({
        filter: { accountId: { eq: foundAccountId } }
      })

      // Process scorecards and load sections/scores in parallel
      const scorecardsWithCounts = await Promise.all(
        initialScorecards.data
          .filter(s => s.accountId === foundAccountId)
          .map(async scorecard => {
            const sectionsResult = await scorecard.sections();
            const sections = sectionsResult.data || [];
            
            // Load all scores for each section in parallel using fetchAllScoresForSection
            const sectionsWithScores = await Promise.all(
              sections.map(async section => {
                // Use fetchAllScoresForSection instead of section.scores() to ensure all scores are fetched
                const allScores = await fetchAllScoresForSection(section.id);
                return {
                  id: section.id,
                  scores: {
                    data: allScores
                  }
                };
              })
            );

            const scoreCount = sectionsWithScores.reduce(
              (total, section) => total + (section.scores.data.length || 0),
              0
            );

            // Store the count in our state object
            setScorecardScoreCounts(prev => ({
              ...prev,
              [scorecard.id]: scoreCount
            }));

            // Load associated example items for this scorecard
            let exampleItems: string[] = [];
            try {
              const associationsResult = await amplifyClient.ScorecardExampleItem.listByScorecard(scorecard.id);
              exampleItems = associationsResult.data.map(association => `item:${association.itemId}`);
              console.log(`Loaded ${exampleItems.length} example items for scorecard ${scorecard.name}:`, exampleItems);
            } catch (error) {
              console.error(`Error loading example items for scorecard ${scorecard.id}:`, error);
            }

            return {
              ...scorecard,
              examples: exampleItems,
              sections: async () => ({
                data: sections,
                nextToken: null
              })
            } as Schema['Scorecard']['type'] & { examples: string[] };
          })
      );

      setScorecards(scorecardsWithCounts);
      setIsLoading(false);
      
      // Return the updated scorecards for immediate use
      return scorecardsWithCounts;
    } catch (error) {
      console.error('Error fetching scorecards:', error)
      setError(error as Error)
      setIsLoading(false)
      return null; // Return null on error
    }
  }

  useEffect(() => {
    fetchScorecards()
  }, [])

  // Removed redundant useEffect for loadScorecardSections - now handled in handleSelectScorecard

  // Helper function to fetch all scores for a section
  const fetchAllScoresForSection = async (sectionId: string) => {
    let allScores: Schema['Score']['type'][] = []
    let nextToken: string | null = null
    
    do {
      const scoresResult = await amplifyClient.Score.list({
        filter: { sectionId: { eq: sectionId } },
        ...(nextToken ? { nextToken } : {})
      })
      

      
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
    
    return allScores
  }

  // Removed fetchSectionsWithScores - functionality moved to handleSelectScorecard

  // Handle creating a new scorecard
  const handleCreate = async () => {
    if (!accountId) return

    const blankScorecard = {
      id: '',
      name: '',
      key: '',
      externalId: '',
      description: '',
      accountId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      account: async () => amplifyClient.Account.get({ id: accountId }),
      sections: async () => ({ 
        data: [],
        nextToken: null
      }),
      evaluations: async () => ({ data: [], nextToken: null }),
      batchJobs: async () => ({ data: [], nextToken: null }),
      item: async () => ({ data: null }),
      scoringJobs: async () => ({ data: [], nextToken: null }),
      scoreResults: async () => ({ data: [], nextToken: null }),
      actions: [],
      datasets: async () => ({ data: [], nextToken: null }),
      tasks: async (): Promise<AmplifyListResult<Schema['Task']['type']>> => {
        return listFromModel<Schema['Task']['type']>(
          client.models.Task,
          { scorecardId: { eq: '' } }
        );
      }
    } as unknown as Schema['Scorecard']['type']

    handleSelectScorecard(blankScorecard);
    setSelectedScorecardSections({ items: [] });
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
    e.preventDefault()
    const startX = e.pageX
    const startWidth = leftPanelWidth

    const handleDrag = (e: MouseEvent) => {
      const delta = e.pageX - startX
      const newWidth = Math.min(Math.max(startWidth + (delta / window.innerWidth) * 100, 30), 70)
      setLeftPanelWidth(newWidth)
    }

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleDragEnd)
    }

    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleDragEnd)
  }

  // Add back the renderSelectedScorecard function
  const renderSelectedScorecard = () => {
    if (!selectedScorecard || !selectedScorecardSections) return null;

    const scorecardData = {
      id: selectedScorecard.id,
      name: selectedScorecard.name,
      key: selectedScorecard.key || '',
      description: selectedScorecard.description || '',
      type: 'scorecard',
      configuration: {},
      order: 0,
      externalId: selectedScorecard.externalId || '',
      sections: selectedScorecardSections || { items: [] },
      // Combine existing examples with newly created ones
      examples: [...(scorecardExamples || [])]
    }

    return (
      <div className={cn(
        "h-full overflow-y-auto overflow-x-hidden",
        maximizedScoreId ? "hidden" : ""
      )}
      style={(selectedScore || selectedItem) && !maximizedScoreId ? {
        width: `${scorecardDetailWidth}%`
      } : { width: '100%' }}>
        <ScorecardComponent
          variant="detail"
          score={scorecardData}
          onEdit={() => handleEdit(selectedScorecard)}
          onViewData={() => {
            setSelectedScorecardForDataset(selectedScorecard.id)
            setShowDatasetConfig(true)
          }}
          isFullWidth={isFullWidth}
          onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
          onClose={handleCloseScorecard}
          onSave={async () => {
            await fetchScorecards()
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
        />
      </div>
    );
  };

  // Memoize the processed score data to ensure stable rendering
  const processedScore = React.useMemo(() => {
    if (!selectedScore) return null;
    
    // Pre-process the score data to ensure name and description render together
    return {
      id: selectedScore.id,
      name: selectedScore.name,
      description: selectedScore.description || '',
      type: selectedScore.type,
      order: selectedScore.order,
      key: selectedScore.key || ''
    };
  }, [selectedScore]);

  // Add back the renderSelectedScore function
  const renderSelectedScore = () => {
    if (!selectedScore || !processedScore) return null;

    return (
      <div className={cn(
        "h-full overflow-y-auto overflow-x-hidden",
        maximizedScoreId ? "w-full" : ""
      )}
      style={!maximizedScoreId ? {
        width: `${100 - scorecardDetailWidth}%`
      } : undefined}>
        <ScoreComponent
          score={processedScore}
          variant="detail"
          isFullWidth={maximizedScoreId === selectedScore.id}
          onToggleFullWidth={() => setMaximizedScoreId(maximizedScoreId ? null : selectedScore.id)}
          onClose={() => {
            setSelectedScore(null);
            setMaximizedScoreId(null);
          }}
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
    <div className="@container flex flex-col h-full p-2 overflow-hidden">
      <div className="flex flex-1 min-h-0">
        {/* Grid Panel */}
        <div 
          className={cn(
            "h-full overflow-auto",
            selectedScore || (selectedScorecard && isFullWidth) ? "hidden" : selectedScorecard ? "flex" : "w-full",
            "transition-all duration-200"
          )}
          style={selectedScorecard && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}
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
              <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-4">
                {scorecards
                  .sort((a, b) => a.name.localeCompare(b.name))
                  .map(scorecard => {
                    const scorecardData = {
                      id: scorecard.id,
                      name: scorecard.name,
                      key: scorecard.key || '',
                      description: scorecard.description || '',
                      type: 'scorecard',
                      configuration: {},
                      order: 0,
                      externalId: scorecard.externalId || '',
                      scoreCount: scorecardScoreCounts[scorecard.id] || 0
                    }

                    return (
                      <div
                        key={scorecard.id}
                        ref={(el) => {
                          scorecardRefsMap.current.set(scorecard.id, el);
                        }}
                      >
                        <ScorecardComponent
                          variant="grid"
                          score={scorecardData}
                          isSelected={selectedScorecard?.id === scorecard.id}
                          onClick={() => handleSelectScorecard(scorecard)}
                          onEdit={() => handleEdit(scorecard)}
                        />
                      </div>
                    )
                  })}
              </div>
            </div>
          </div>
        </div>

        {/* Resize Handle between Grid and Detail */}
        {selectedScorecard && !isFullWidth && !selectedScore && (
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
          {renderSelectedScorecard()}
          
          {/* Resize Handle between Scorecard and Score/Item */}
          {(selectedScore || selectedItem) && !maximizedScoreId && (
            <div
              className="w-[12px] relative cursor-col-resize flex-shrink-0 group mx-1"
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
                  const newDetailWidth = Math.min(Math.max(startDetailWidth + deltaPercent, 30), 70)
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
          
          {renderSelectedScore()}
          {renderSelectedItem()}
        </div>
      </div>

      {showDatasetConfig && selectedScorecardForDataset && (
        <DatasetConfigFormComponent
          scorecardId={selectedScorecardForDataset}
          onClose={() => {
            setShowDatasetConfig(false)
            setSelectedScorecardForDataset("")
          }}
        />
      )}
    </div>
  )
}


import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, Pencil, Database, ListChecks, X, Square, Columns2, Plus, ChevronUp, ChevronDown, ListCheck, ChevronRight, FileText, Key, StickyNote, Edit, IdCard, TestTube, MessageCircleMore, Coins, Expand } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { EditableField } from '@/components/ui/editable-field'
import { amplifyClient } from '@/utils/amplify-client'
import { graphqlRequest } from '@/utils/amplify-client'
import type { Schema } from '@/amplify/data/resource'
import { ScoreComponent } from '@/components/ui/score-component'
import { toast } from "sonner"
import { EditableHeader } from '@/components/ui/editable-header'
import { createTask } from '@/utils/data-operations'
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { useAccount } from '@/app/contexts/AccountContext'
import { TestItemDialog } from './test-item-dialog'
import Editor from "@monaco-editor/react"
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions } from "@/lib/monaco-theme"
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { GuidelinesEditor, FullscreenGuidelinesEditor } from '@/components/ui/guidelines-editor'
import { ScoreHeaderInfo, type ScoreHeaderData } from '@/components/ui/score-header-info'

export interface ScorecardData {
  id: string
  name: string
  key: string
  description: string
  guidelines?: string
  type: string
  order: number
  externalId?: string
  scoreCount?: number
  isCountLoading?: boolean
  icon?: React.ReactNode
  examples?: string[]
  sections?: {
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
          guidelines?: string
          order: number
          type: string
        }>
      }
    }>
  }
}

interface ScorecardComponentProps extends React.HTMLAttributes<HTMLDivElement> {
  score: ScorecardData
  onEdit?: () => void
  onViewData?: () => void
  onFeedbackAnalysis?: () => void
  onCostAnalysis?: () => void
  isSelected?: boolean
  onClick?: () => void
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  variant?: 'grid' | 'detail'
  onSave?: () => void
  onScoreSelect?: (score: any, sectionId: string) => void
  selectedScoreId?: string
  onCreateItem?: (initialContent?: string) => void
  onEditItem?: (itemId: string) => void
  shouldExpandExamples?: boolean
  onExamplesExpanded?: () => void
  onTaskCreated?: (task: any) => void
  onCreateScore?: (sectionId: string) => void
}

const GridContent = React.memo(({ 
  score,
  isSelected 
}: { 
  score: ScorecardData
  isSelected?: boolean
}) => {
  const scoreCount = score.scoreCount
  const isCountLoading = score.isCountLoading || false
  const hasLoadedCount = scoreCount !== undefined

  // Determine display text and styling
  let displayText: string
  let textColor: string

  if (!hasLoadedCount) {
    displayText = "- Scores"
    textColor = "text-muted-foreground" // Dim when unknown
  } else {
    const scoreText = scoreCount === 1 ? 'Score' : 'Scores'
    displayText = `${scoreCount} ${scoreText}`
    textColor = "text-foreground" // Normal foreground when loaded
  }

  return (
    <div className="flex justify-between items-start w-full">
      <div className="space-y-1.5">
        <div className="font-medium">{score.name}</div>
        <div className="text-sm text-muted-foreground flex items-center gap-1">
          <IdCard className="h-3 w-3" />
          <span>{score.externalId || '-'}</span>
        </div>
        <div className={`text-sm ${textColor}`}>
          <span>{displayText}</span>
        </div>
      </div>
      <div className="flex flex-col items-center gap-1">
        <div className="text-muted-foreground">
          {score.icon || <ListChecks className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />}
        </div>
        <div className="text-xs text-muted-foreground text-center">Scorecard</div>
      </div>
    </div>
  )
})

interface DetailContentProps {
  score: ScorecardData
  isFullWidth: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onViewData?: () => void
  onFeedbackAnalysis?: () => void
  onCostAnalysis?: () => void
  onEdit?: () => void
  onEditChange?: (changes: Partial<ScorecardData>) => void
  onAddSection?: () => void
  onMoveSection?: (index: number, direction: 'up' | 'down') => void
  onDeleteSection?: (index: number) => void
  onSave?: () => void
  onCancel?: () => void
  hasChanges?: boolean
  onScoreSelect?: (score: any, sectionId: string) => void
  selectedScoreId?: string
  onCreateItem?: (initialContent?: string) => void
  onEditItem?: (itemId: string) => void
  shouldExpandExamples?: boolean
  onExamplesExpanded?: () => void
  onTaskCreated?: (task: any) => void
  onCreateScore?: (sectionId: string) => void
  onOpenGuidelinesEditor?: () => void
  onStartInlineEdit?: () => void
  isGuidelinesEditing?: boolean
  guidelinesEditValue?: string
  hasGuidelinesChanges?: boolean
  isSavingGuidelines?: boolean
  onGuidelinesChange?: (value: string) => void
  onSaveGuidelines?: () => void
  onCancelGuidelinesEdit?: () => void
}

export const DetailContent = React.memo(function DetailContent({
  score,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  onViewData,
  onFeedbackAnalysis,
  onCostAnalysis,
  onEditChange,
  onAddSection,
  onMoveSection,
  onDeleteSection,
  onSave,
  onCancel,
  hasChanges,
  onScoreSelect,
  selectedScoreId,
  onCreateItem,
  onEditItem,
  shouldExpandExamples,
  onExamplesExpanded,
  onTaskCreated,
  onCreateScore,
  onOpenGuidelinesEditor,
  onStartInlineEdit,
  isGuidelinesEditing,
  guidelinesEditValue,
  hasGuidelinesChanges,
  isSavingGuidelines,
  onGuidelinesChange,
  onSaveGuidelines,
  onCancelGuidelinesEdit
}: DetailContentProps) {
  const { selectedAccount } = useAccount()
  const [sectionNameChanges, setSectionNameChanges] = React.useState<Record<string, string>>({})
  const [isExamplesExpanded, setIsExamplesExpanded] = React.useState(false)
  const [isGuidelinesExpanded, setIsGuidelinesExpanded] = React.useState(false)
  const [isAddingByExternalId, setIsAddingByExternalId] = React.useState(false)
  const [externalIdSearch, setExternalIdSearch] = React.useState("")
  const [searchResults, setSearchResults] = React.useState<Array<{id: string, externalId: string, description?: string}>>([])
  const [isSearching, setIsSearching] = React.useState(false)
  const [itemToRemove, setItemToRemove] = React.useState<{index: number, example: string} | null>(null)
  const [itemDetails, setItemDetails] = React.useState<Record<string, {externalId?: string, description?: string}>>({})
  const [loadingItemDetails, setLoadingItemDetails] = React.useState<Set<string>>(new Set())
  const [testItemDialog, setTestItemDialog] = React.useState<{
    isOpen: boolean
    itemId: string
    displayValue: string
  }>({ isOpen: false, itemId: '', displayValue: '' })

  // Fetch item details for display when examples change
  React.useEffect(() => {
    const fetchItemDetails = async () => {
      if (!score.examples) return;
      
      const itemRefs = score.examples.filter(ex => ex.startsWith('item:'));
      const itemIds = itemRefs.map(ref => ref.substring(5));
      
      for (const itemId of itemIds) {
        if (!itemDetails[itemId] && !loadingItemDetails.has(itemId)) {
          setLoadingItemDetails(prev => new Set(Array.from(prev).concat(itemId)));
          try {
            const result = await amplifyClient.Item.get({ id: itemId });
            if (result.data) {
              setItemDetails(prev => ({
                ...prev,
                [itemId]: {
                  externalId: result.data?.externalId || undefined,
                  description: result.data?.description || undefined
                }
              }));
            }
          } catch (error) {
            console.error(`Error fetching item ${itemId}:`, error);
            // Still set empty details to avoid infinite loading
            setItemDetails(prev => ({
              ...prev,
              [itemId]: {}
            }));
          } finally {
            setLoadingItemDetails(prev => {
              const newSet = new Set(prev);
              newSet.delete(itemId);
              return newSet;
            });
          }
        }
      }
    };

    fetchItemDetails();
  }, [score.examples, itemDetails, loadingItemDetails]);

  // Auto-expand examples when a new item is created
  React.useEffect(() => {
    if (shouldExpandExamples && !isExamplesExpanded) {
      setIsExamplesExpanded(true);
      // Call the callback to reset the expand flag
      onExamplesExpanded?.();
    }
  }, [shouldExpandExamples, isExamplesExpanded, onExamplesExpanded]);

  // Debounce timer for section name changes
  const sectionNameDebounceTimers = React.useRef<Record<string, NodeJS.Timeout>>({})
  
  const handleSectionNameChange = (sectionId: string, newName: string) => {
    setSectionNameChanges(prev => ({
      ...prev,
      [sectionId]: newName
    }))
    
    const sectionIndex = score.sections?.items?.findIndex(s => s.id === sectionId) ?? -1
    if (sectionIndex >= 0) {
      const updatedSections = [...(score.sections?.items || [])]
      updatedSections[sectionIndex] = { 
        ...updatedSections[sectionIndex], 
        name: newName 
      }
      onEditChange?.({ sections: { items: updatedSections } })
      
      // Debounce the database update (wait 1 second after user stops typing)
      if (sectionNameDebounceTimers.current[sectionId]) {
        clearTimeout(sectionNameDebounceTimers.current[sectionId])
      }
      
      sectionNameDebounceTimers.current[sectionId] = setTimeout(async () => {
        try {
          console.log('💾 Updating section name in database:', newName)
          await amplifyClient.ScorecardSection.update({
            id: sectionId,
            name: newName
          })
          console.log('💾 Section name updated successfully')
        } catch (error) {
          console.error('❌ Error updating section name:', error)
          toast.error('Failed to update section name')
        }
      }, 1000) // Wait 1 second after user stops typing
    }
  }

  const handleDeleteSectionClick = (section: {
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
  }, index: number) => {
    console.log('Delete section clicked:', { section, index })
    const scoreCount = section.scores?.items?.length || 0
    console.log('Score count:', scoreCount)
    if (scoreCount > 0) {
      console.log('Showing toast for non-empty section')
      toast.error(`Cannot delete "${section.name}" because it contains ${scoreCount} score${scoreCount === 1 ? '' : 's'}. Please remove all scores first.`)
      return
    }
    console.log('Calling onDeleteSection with index:', index)
    onDeleteSection?.(index)
  }

  const handleAddByExternalId = async () => {
    if (externalIdSearch.trim() && selectedAccount) {
      try {
        setIsSearching(true);
        
        console.log('🔍 Starting search with:', {
          externalId: externalIdSearch.trim(),
          accountId: selectedAccount.id,
          selectedAccount: selectedAccount
        });
        
        // Use the listItemByExternalId query that works
        let searchResponse = await graphqlRequest<{
          listItemByExternalId: {
            items: Array<{
              id: string;
              externalId: string;
              description?: string;
              accountId: string;
            }>;
          };
        }>(`
          query SearchByExternalId($externalId: String!) {
            listItemByExternalId(externalId: $externalId) {
              items {
                id
                externalId
                description
                accountId
              }
            }
          }
        `, {
          externalId: externalIdSearch.trim()
        });

        console.log('📡 Search response from listItemByExternalId:', {
          data: searchResponse.data,
          errors: searchResponse.errors
        });

        // Filter results by account
        let items = searchResponse.data?.listItemByExternalId?.items || [];
        console.log('📋 All items found:', items);
        
        // Filter by the selected account
        const accountFilteredItems = items.filter(item => item.accountId === selectedAccount.id);
        console.log('📋 Items filtered by account:', accountFilteredItems);
        
        // If no items in the selected account, try a broader search without account filter
        if (accountFilteredItems.length === 0 && items.length > 0) {
          console.log('⚠️ Items found but not in selected account. Items belong to accounts:', 
            items.map(item => item.accountId));
          toast.error(`Item "${externalIdSearch.trim()}" found, but it belongs to a different account. Please check your account selection.`);
          setSearchResults([]);
          return;
        }
        
        items = accountFilteredItems;
        setSearchResults(items);
        
        if (items.length === 0) {
          console.log('❌ No items found');
          toast.error("No items found with that external ID");
        } else if (items.length === 1) {
          console.log('✅ One item found, auto-selecting:', items[0]);
          // If only one item found, auto-select it
          await associateItem(items[0]);
        } else {
          console.log('📝 Multiple items found, showing results for selection');
        }
        
      } catch (error) {
        console.error('💥 Error searching for items:', error);
        toast.error("Failed to search for items");
      } finally {
        setIsSearching(false);
      }
    } else if (!selectedAccount) {
      console.log('⚠️ No account selected');
      toast.error("No account selected");
    } else {
      console.log('⚠️ No external ID provided');
    }
  };

  const associateItem = async (item: {id: string, externalId: string, description?: string}) => {
    try {
      // Check if association already exists
      const existingAssociations = await amplifyClient.ScorecardExampleItem.listByScorecard(score.id);
      const existingAssociation = existingAssociations.data.find(assoc => assoc.itemId === item.id);

      if (existingAssociation) {
        toast.error("This item is already associated with this scorecard");
        return;
      }

      // Create the ScorecardExampleItem association
      await amplifyClient.ScorecardExampleItem.create({
        itemId: item.id,
        scorecardId: score.id,
        addedAt: new Date().toISOString()
      });

      // Add to the examples list for UI display
      onEditChange?.({ 
        examples: [...(score.examples || []), `item:${item.id}`] 
      });

      // Clear the search
      setExternalIdSearch("");
      setSearchResults([]);
      setIsAddingByExternalId(false);
      toast.success(`Item "${item.externalId}" successfully associated with scorecard`);
    } catch (error) {
      console.error('Error associating item with scorecard:', error);
      toast.error("Failed to associate item with scorecard");
    }
  };

  const cancelAddingExample = () => {
    setIsAddingByExternalId(false);
    setExternalIdSearch("");
    setSearchResults([]);
    setIsSearching(false);
  };

  const handleRemoveItem = async (index: number, example: string) => {
    const updatedExamples = [...(score.examples || [])];
    updatedExamples.splice(index, 1);
    onEditChange?.({ examples: updatedExamples });

    // If this is an item reference, we need to remove the association from the ScorecardExampleItem table
    if (example.startsWith('item:')) {
      const itemId = example.substring(5);
      try {
        // Delete the ScorecardExampleItem association
        await amplifyClient.ScorecardExampleItem.delete({
          itemId: itemId,
          scorecardId: score.id
        });
        toast.success("Item removed from scorecard successfully");
      } catch (error) {
        console.error('Error removing item from scorecard:', error);
        toast.error("Failed to remove item association. The item was removed from the list but may still be associated.");
      }
    }
    
    setItemToRemove(null);
  };

  const handleTestItem = (itemId: string, displayValue: string) => {
    setTestItemDialog({
      isOpen: true,
      itemId,
      displayValue
    });
  };

  const handleTestItemWithScore = async (scoreId: string) => {
    console.log('Testing item with score:', { itemId: testItemDialog.itemId, scoreId });
    
    try {
      // Find the selected score details
      const selectedScore = availableScores.find(s => s.id === scoreId);
      if (!selectedScore) {
        toast.error("Selected score not found");
        return;
      }

      // Create the prediction command using correct CLI parameter names
      const command = `predict --scorecard "${score.name}" --score "${selectedScore.name}" --item "${testItemDialog.itemId}" --format json`;
      
      // Create the task
      const task = await createTask({
        type: 'Prediction Test',
        target: 'prediction',
        command: command,
        accountId: selectedAccount?.id || 'call-criteria',
        dispatchStatus: 'PENDING',
        status: 'PENDING',
        scorecardId: score.id,
        scoreId: scoreId
      });

      // If task was created successfully, update the command to include the task-id
      if (task) {
        const commandWithTaskId = `predict --scorecard "${score.name}" --score "${selectedScore.name}" --item "${testItemDialog.itemId}" --format json --task-id "${task.id}"`;
        
        // Update the task with the command that includes task-id for progress tracking
        // Note: This would require an updateTask call, but for now we'll use the original command
        // The backend can handle task tracking via the task-id parameter when implemented
      }

      if (task) {
        toast.success("Prediction test task created", {
          description: <span className="font-mono text-sm truncate block">{command}</span>
        });
        
        // Notify parent component about task creation
        onTaskCreated?.(task);
      } else {
        toast.error("Failed to create prediction test task");
      }
    } catch (error) {
      console.error('Error creating prediction test task:', error);
      toast.error("Error creating prediction test task");
    }
  };

  const closeTestItemDialog = () => {
    setTestItemDialog({ isOpen: false, itemId: '', displayValue: '' });
  };

  // Get available scores from all sections
  const availableScores = React.useMemo(() => {
    if (!score.sections?.items) return [];
    
    return score.sections.items.flatMap(section => 
      section.scores?.items?.map(scoreItem => ({
        id: scoreItem.id,
        name: scoreItem.name,
        sectionName: section.name
      })) || []
    );
  }, [score.sections]);

  return (
    <div className="w-full flex flex-col min-h-0">
      {/* Header with title and actions */}
      <div className="flex justify-between items-center w-full mb-3">
        <div className="flex items-center gap-2">
          <ListChecks className="h-5 w-5 text-foreground" />
          <span className="text-lg font-semibold">Scorecard</span>
        </div>
        <div className="flex gap-2">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <div onClick={(e) => e.stopPropagation()}>
                <CardButton
                  icon={MoreHorizontal}
                  onClick={() => {}}
                  aria-label="More options"
                />
              </div>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content 
                align="end" 
                className="min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md z-50"
                onClick={(e) => e.stopPropagation()}
              >
                {onViewData && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={() => {
                      onViewData();
                    }}
                  >
                    <Database className="mr-2 h-4 w-4" />
                    View Data
                  </DropdownMenu.Item>
                )}
                {onFeedbackAnalysis && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={() => {
                      onFeedbackAnalysis();
                    }}
                  >
                    <MessageCircleMore className="mr-2 h-4 w-4" />
                    Analyze Feedback
                  </DropdownMenu.Item>
                )}
                {onCostAnalysis && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={() => {
                      onCostAnalysis();
                    }}
                  >
                    <Coins className="mr-2 h-4 w-4" />
                    Analyze Cost
                  </DropdownMenu.Item>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          {onToggleFullWidth && (
            <CardButton
              icon={isFullWidth ? Columns2 : Square}
              onClick={onToggleFullWidth}
              aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
            />
          )}
          {onClose && (
            <CardButton
              icon={X}
              onClick={onClose}
              aria-label="Close"
            />
          )}
        </div>
      </div>

      {/* Full-width header info */}
      <div className="w-full">
        <ScoreHeaderInfo
          data={{
            name: score.name || '',
            description: score.description || '',
            key: score.key || '',
            externalId: score.externalId || ''
          }}
          onChange={(changes: Partial<ScoreHeaderData>) => {
            onEditChange?.(changes);
          }}
          namePlaceholder="Scorecard Name"
          descriptionPlaceholder="No description"
          keyPlaceholder="scorecard-key"
          externalIdPlaceholder="External ID"
        />
      </div>

      {hasChanges && (
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={onSave}>Save Changes</Button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto mt-6 w-full">
        <div className="space-y-6 w-full">


          {/* Guidelines Section */}
          <GuidelinesEditor
            guidelines={isGuidelinesEditing ? guidelinesEditValue : score.guidelines}
            isEditing={isGuidelinesEditing}
            isExpanded={isGuidelinesExpanded}
            onToggleExpanded={() => setIsGuidelinesExpanded(!isGuidelinesExpanded)}
            onStartInlineEdit={onStartInlineEdit}
            onOpenFullscreenEditor={onOpenGuidelinesEditor}
            onGuidelinesChange={onGuidelinesChange}
            onSaveGuidelines={onSaveGuidelines}
            onCancelEdit={onCancelGuidelinesEdit}
            hasChanges={hasGuidelinesChanges}
            isSaving={isSavingGuidelines}
          />

          <div>
            <div className="flex justify-between items-center mb-2">
              <div className="flex items-center">
                <h3 
                  className="text-sm font-medium cursor-pointer flex items-center"
                  onClick={() => setIsExamplesExpanded(!isExamplesExpanded)}
                >
                  Example Items
                  <span className="ml-2 text-muted-foreground text-base font-normal">
                    ({score.examples?.length || 0})
                  </span>
                  {isExamplesExpanded ? (
                    <ChevronDown className="h-4 w-4 ml-2 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 ml-2 text-muted-foreground" />
                  )}
                </h3>
              </div>
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <div>
                    <CardButton
                      icon={Plus}
                      label="Add Example"
                      onClick={() => {}}
                    />
                  </div>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content align="end" className="min-w-[300px] overflow-hidden rounded-md border bg-popover p-2 text-popover-foreground shadow-md z-50">
                    <DropdownMenu.Item 
                      className="relative flex cursor-default select-none items-center rounded-sm px-3 py-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                      onSelect={() => {
                        setIsExamplesExpanded(true);
                        setIsAddingByExternalId(true);
                      }}
                    >
                      <Key className="mr-2 h-4 w-4" />
                      <div>
                        <div>Add by External ID</div>
                        <div className="text-xs text-muted-foreground">Reference an existing item by its external ID</div>
                      </div>
                    </DropdownMenu.Item>
                    <DropdownMenu.Item 
                      className="relative flex cursor-default select-none items-center rounded-sm px-3 py-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                      onSelect={() => {
                        // Immediately trigger item creation without showing inline form
                        onCreateItem?.('');
                      }}
                    >
                      <FileText className="mr-2 h-4 w-4" />
                      <div>
                        <div>Add by Content</div>
                        <div className="text-xs text-muted-foreground">Create a new example with specific content</div>
                      </div>
                    </DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </div>
            
            {isExamplesExpanded && (
              <div className="mb-6">
                {isAddingByExternalId && (
                  <div className="bg-muted/20 p-3 rounded-md mb-3">
                    <h4 className="text-sm font-medium mb-2">Add example by External ID</h4>
                    <p className="text-xs text-muted-foreground mb-2">
                      Use an existing item from your account by entering its external ID.
                    </p>
                    <div className="flex gap-2 items-center">
                      <Input
                        placeholder="Enter external ID"
                        value={externalIdSearch}
                        onChange={(e) => setExternalIdSearch(e.target.value)}
                        className="flex-1"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            handleAddByExternalId();
                          }
                        }}
                      />
                      <Button 
                        size="sm" 
                        onClick={handleAddByExternalId}
                        disabled={isSearching || !externalIdSearch.trim()}
                      >
                        {isSearching ? 'Searching...' : 'Search'}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={cancelAddingExample}>
                        Cancel
                      </Button>
                    </div>
                    
                    {/* Search Results */}
                    {searchResults.length > 1 && (
                      <div className="mt-3">
                        <p className="text-xs text-muted-foreground mb-2">
                          Found {searchResults.length} items. Select one to associate:
                        </p>
                        <div className="space-y-1 max-h-32 overflow-y-auto">
                          {searchResults.map((item) => (
                            <div 
                              key={item.id}
                              className="flex items-center justify-between p-2 border rounded-md hover:bg-accent cursor-pointer"
                              onClick={() => associateItem(item)}
                            >
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{item.externalId}</p>
                                {item.description && (
                                  <p className="text-xs text-muted-foreground truncate">{item.description}</p>
                                )}
                              </div>
                              <Button size="sm" variant="ghost">
                                Add
                              </Button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {(!score.examples || score.examples.length === 0) && !isAddingByExternalId ? (
                  <div className="text-center text-muted-foreground py-4">
                    <p>No example items yet</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {score.examples?.map((example, index) => {
                      const isItemReference = example.startsWith('item:');
                      let displayValue: string;
                      
                      if (isItemReference) {
                        const itemId = example.substring(5);
                        const details = itemDetails[itemId];
                        if (loadingItemDetails.has(itemId)) {
                          displayValue = `Item: Loading...`;
                        } else if (details?.externalId) {
                          displayValue = `Item: ${details.externalId}`;
                        } else {
                          displayValue = `Item: ${itemId}`;
                        }
                      } else if (example.startsWith('content:')) {
                        displayValue = example.substring(8);
                      } else {
                        displayValue = example;
                      }
                      
                      return (
                        <div key={index} className="flex items-center justify-between p-2 bg-background rounded-md">
                          <div className="flex items-center">
                            <StickyNote className="h-4 w-4 mr-2 text-muted-foreground" />
                            <span>{displayValue}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              onClick={() => {
                                if (isItemReference) {
                                  const itemId = example.substring(5);
                                  handleTestItem(itemId, displayValue);
                                } else {
                                  // For content-based examples, use the example itself as the display value
                                  handleTestItem(example, displayValue);
                                }
                              }}
                              title="Test with this item"
                            >
                              <TestTube className="h-4 w-4" />
                            </Button>
                            {isItemReference && onEditItem && (
                              <Button 
                                variant="ghost" 
                                size="icon" 
                                onClick={() => {
                                  const itemId = example.substring(5);
                                  onEditItem(itemId);
                                }}
                                title="Edit item"
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                            )}
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              onClick={() => setItemToRemove({index, example})}
                              title="Remove from scorecard"
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {!score.sections ? (
            // Loading state when sections haven't been loaded yet
            <div className="space-y-4">
              <div className="text-sm text-muted-foreground">Loading sections...</div>
              {Array.from({ length: 2 }).map((_, i) => (
                <div key={i} className="space-y-3">
                  <div className="h-6 bg-muted animate-pulse rounded"></div>
                  <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-4">
                    {Array.from({ length: 3 }).map((_, j) => (
                      <div key={j} className="h-24 bg-muted animate-pulse rounded"></div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : score.sections.items.length === 0 ? (
            // Empty state when no sections exist
            <div className="text-center py-8 text-muted-foreground">
              <ListChecks className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No sections found</p>
            </div>
          ) : (
            // Normal rendering when sections are loaded
            score.sections.items.map((section, index) => {
            // Process scores for this section
            const processedScores = section.scores?.items?.map((score) => ({
              id: score.id,
              name: score.name,
              description: score.description || '',
              type: score.type,
              order: score.order,
              key: score.key || '',
              externalId: (score as any).externalId || score.id,
              icon: <ListCheck className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
            })) || [];
            
            // Sort scores alphabetically by name (case-insensitive)
            const sortedScores = [...processedScores].sort((a, b) => 
              a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
            );
            
            return (
              <div key={section.id} className="space-y-2 w-full">
                <div className="flex justify-between items-center w-full">
                  <div className="flex-1">
                    <EditableHeader
                      value={sectionNameChanges[section.id] ?? section.name}
                      onChange={(value) => handleSectionNameChange(section.id, value)}
                      level="h3"
                      className="text-base"
                    />
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <CardButton
                      icon={X}
                      onClick={() => handleDeleteSectionClick(section, index)}
                    />
                    <CardButton
                      icon={ChevronUp}
                      onClick={() => onMoveSection?.(index, 'up')}
                    />
                    <CardButton
                      icon={ChevronDown}
                      onClick={() => onMoveSection?.(index, 'down')}
                    />
                    <CardButton
                      icon={Plus}
                      label="Create Score"
                      onClick={() => onCreateScore?.(section.id)}
                    />
                  </div>
                </div>
                <div className="bg-background rounded-lg w-full">
                  <div className="@container w-full p-4">
                    <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-4 w-full">
                      {sortedScores.map((scoreData) => (
                        <ScoreComponent
                          key={scoreData.id}
                          variant="grid"
                          score={scoreData}
                          isSelected={selectedScoreId === scoreData.id}
                          onClick={() => onScoreSelect?.(
                            section.scores?.items?.find(s => s.id === scoreData.id),
                            section.id
                          )}
                          exampleItems={score.examples?.map((example, index) => {
                            const isItemReference = example.startsWith('item:');
                            let displayValue: string;
                            
                            if (isItemReference) {
                              const itemId = example.substring(5);
                              const details = itemDetails[itemId];
                              if (loadingItemDetails.has(itemId)) {
                                displayValue = `Item: Loading...`;
                              } else if (details?.externalId) {
                                displayValue = `Item: ${details.externalId}`;
                              } else {
                                displayValue = `Item: ${itemId}`;
                              }
                            } else if (example.startsWith('content:')) {
                              displayValue = example.substring(8);
                            } else {
                              displayValue = example;
                            }
                            
                            return {
                              id: isItemReference ? example.substring(5) : `content_${index}`,
                              displayValue
                            };
                          }) || []}
                          scorecardName={score.name}
                          onTaskCreated={onTaskCreated}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          }))}
          <div className="flex justify-end w-full">
            <CardButton
              icon={Plus}
              label="Create Section"
              onClick={() => onAddSection?.()}
            />
          </div>
        </div>
      </div>

      {/* Confirmation dialog for removing items */}
      <AlertDialog open={!!itemToRemove} onOpenChange={() => setItemToRemove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Item from Scorecard</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove this item from the scorecard? 
              {itemToRemove?.example.startsWith('item:') && " This will remove the association between the item and this scorecard."}
              {" "}You can add it back again later if needed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction 
              onClick={() => itemToRemove && handleRemoveItem(itemToRemove.index, itemToRemove.example)}
            >
              Remove Item
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Test Item Dialog */}
      <TestItemDialog
        isOpen={testItemDialog.isOpen}
        onClose={closeTestItemDialog}
        onTest={handleTestItemWithScore}
        itemDisplayValue={testItemDialog.displayValue}
        availableScores={availableScores}
      />
    </div>
  )
})

export default function ScorecardComponent({ 
  score, 
  onEdit, 
  onViewData, 
  onFeedbackAnalysis,
  onCostAnalysis,
  variant = 'grid', 
  isSelected,
  onClick,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  onSave,
  onScoreSelect,
  selectedScoreId,
  onCreateItem,
  onEditItem,
  shouldExpandExamples,
  onExamplesExpanded,
  onTaskCreated,
  onCreateScore,
  className, 
  ...props 
}: ScorecardComponentProps) {
  const [editedScore, setEditedScore] = React.useState<ScorecardData>(score)
  const [hasChanges, setHasChanges] = React.useState(false)
  const [isGuidelinesFullscreen, setIsGuidelinesFullscreen] = React.useState(false)
  const [isGuidelinesEditing, setIsGuidelinesEditing] = React.useState(false)
  const [guidelinesEditValue, setGuidelinesEditValue] = React.useState('')
  const [hasGuidelinesChanges, setHasGuidelinesChanges] = React.useState(false)
  const [isSavingGuidelines, setIsSavingGuidelines] = React.useState(false)
  const previewRef = React.useRef<HTMLDivElement>(null)
  const editorRef = React.useRef<any>(null)

  // Track the previous scorecard ID to detect when we switch to a different scorecard
  const prevScoreIdRef = React.useRef<string | null>(null)

  React.useEffect(() => {
    console.log('🔍 ScorecardComponent received score:', {
      id: score.id,
      name: score.name,
      guidelines: score.guidelines,
      guidelinesType: typeof score.guidelines,
      guidelinesLength: score.guidelines?.length,
      hasGuidelines: 'guidelines' in score,
      allScoreFields: Object.keys(score)
    });
    
    // Update editedScore in two cases:
    // 1. We're switching to a different scorecard (different ID)
    // 2. We're on the same scorecard but have no unsaved changes (data was refreshed after save)
    if (prevScoreIdRef.current !== score.id) {
      console.log('🔄 Switching to different scorecard, resetting editedScore');
      setEditedScore(score)
      setHasChanges(false)
      prevScoreIdRef.current = score.id
    } else if (!hasChanges) {
      // Same scorecard, no unsaved changes - update with fresh data from server
      console.log('🔄 Updating editedScore with fresh data from server (no unsaved changes)');
      setEditedScore(score)
    }
  }, [score, hasChanges])

  const handleEditChange = (changes: Partial<ScorecardData>) => {
    setEditedScore(prev => {
      const updated = { ...prev, ...changes }
      // Only set hasChanges if name, key, externalId, description, sections, or guidelines were changed
      if ('name' in changes || 'key' in changes || 'externalId' in changes || 'description' in changes || 'sections' in changes || 'examples' in changes || 'guidelines' in changes) {
        setHasChanges(true)
      }
      return updated
    })
  }

  const handleOpenGuidelinesEditor = () => {
    setGuidelinesEditValue(editedScore.guidelines || '')
    setHasGuidelinesChanges(false)
    setIsGuidelinesFullscreen(true)
  }

  const handleStartInlineEdit = () => {
    setGuidelinesEditValue(editedScore.guidelines || '')
    setHasGuidelinesChanges(false)
    setIsGuidelinesEditing(true)
  }

  const handleSaveGuidelines = async () => {
    if (isSavingGuidelines) return; // Prevent double-clicks
    
    try {
      setIsSavingGuidelines(true);
      console.log('🔧 handleSaveGuidelines called - Saving guidelines:', {
        scorecardId: editedScore.id,
        scorecardName: editedScore.name,
        guidelines: guidelinesEditValue,
        guidelinesLength: guidelinesEditValue.length,
        source: 'handleSaveGuidelines function'
      });

      // First, save to database via amplify client
      console.log('🔧 Updating scorecard in database...');
      await amplifyClient.Scorecard.update({
        id: editedScore.id,
        guidelines: guidelinesEditValue
      });
      console.log('🔧 Database update completed');

      // Update the local editedScore with the new guidelines
      handleEditChange({ guidelines: guidelinesEditValue })
      setIsGuidelinesFullscreen(false)
      setIsGuidelinesEditing(false)
      setHasGuidelinesChanges(false)
      
      // Auto-save if there's an onSave handler (this will refresh the data)
      if (onSave) {
        console.log('🔧 Calling onSave handler...');
        await onSave()
        console.log('🔧 onSave completed');
      }
      
      toast.success('Guidelines saved successfully')
    } catch (error) {
      console.error('Error saving guidelines:', error)
      toast.error('Failed to save guidelines')
    } finally {
      setIsSavingGuidelines(false);
    }
  }

  const handleCancelGuidelinesEdit = () => {
    setGuidelinesEditValue(editedScore.guidelines || '')
    setHasGuidelinesChanges(false)
    setIsGuidelinesFullscreen(false)
    setIsGuidelinesEditing(false)
    // Clear refs when closing
    editorRef.current = null
  }

  const handleGuidelinesChange = (value: string | undefined) => {
    setGuidelinesEditValue(value || '')
    setHasGuidelinesChanges((value || '') !== (editedScore.guidelines || ''))
  }

  // Synchronized scrolling handler
  const handleEditorScroll = React.useCallback(() => {
    if (!editorRef.current || !previewRef.current) return
    
    const editor = editorRef.current
    const preview = previewRef.current
    
    // Get scroll position as percentage of total scrollable height
    const scrollTop = editor.getScrollTop()
    const scrollHeight = editor.getScrollHeight()
    const clientHeight = editor.getLayoutInfo().height
    const maxScroll = scrollHeight - clientHeight
    
    if (maxScroll <= 0) return
    
    const scrollPercentage = scrollTop / maxScroll
    
    // Apply the same scroll percentage to preview
    const previewMaxScroll = preview.scrollHeight - preview.clientHeight
    if (previewMaxScroll > 0) {
      preview.scrollTop = scrollPercentage * previewMaxScroll
    }
  }, [])

  const handleAddSection = async () => {
    try {
      const maxOrder = Math.max(0, ...(editedScore.sections?.items || []).map(s => s.order))
      
      // Create the section in the database immediately
      console.log('💾 Creating new section in database...')
      const newSectionResult = await amplifyClient.ScorecardSection.create({
        name: "New section",
        order: maxOrder + 1,
        scorecardId: editedScore.id
      })
      
      if (!newSectionResult.data) {
        throw new Error('Failed to create section')
      }
      
      console.log('💾 New section created with ID:', newSectionResult.data.id)
      
      // Add the new section with its real database ID
      const newSection = {
        id: newSectionResult.data.id,
        name: newSectionResult.data.name,
        order: newSectionResult.data.order,
        scores: { items: [] }
      }
      
      setEditedScore(prev => ({
        ...prev,
        sections: {
          items: [...(prev.sections?.items || []), newSection]
        }
      }))
      
      toast.success('Section created successfully')
    } catch (error) {
      console.error('❌ Error creating section:', error)
      toast.error('Failed to create section: ' + (error instanceof Error ? error.message : 'Unknown error'))
    }
  }

  const handleMoveSection = async (index: number, direction: 'up' | 'down') => {
    if (!editedScore.sections?.items) return

    const newSections = [...editedScore.sections.items]
    const newIndex = direction === 'up' ? index - 1 : index + 1
    
    if (newIndex < 0 || newIndex >= newSections.length) return
    
    const temp = newSections[index]
    newSections[index] = newSections[newIndex]
    newSections[newIndex] = temp
    
    newSections[index].order = index
    newSections[newIndex].order = newIndex
    
    setEditedScore(prev => ({
      ...prev,
      sections: { items: newSections }
    }))
    
    try {
      // Update the order in the database immediately
      console.log('🔄 Updating section order in database...')
      await Promise.all([
        amplifyClient.ScorecardSection.update({
          id: newSections[index].id,
          order: newSections[index].order
        }),
        amplifyClient.ScorecardSection.update({
          id: newSections[newIndex].id,
          order: newSections[newIndex].order
        })
      ])
      console.log('🔄 Section order updated successfully')
    } catch (error) {
      console.error('❌ Error updating section order:', error)
      toast.error('Failed to update section order: ' + (error instanceof Error ? error.message : 'Unknown error'))
    }
  }

  const handleDeleteSection = async (sectionIndex: number) => {
    if (!editedScore.sections?.items) return

    const sectionToDelete = editedScore.sections.items[sectionIndex]
    
    try {
      // Delete the section from the database immediately
      console.log('🗑️ Deleting section from database:', sectionToDelete.name)
      await amplifyClient.ScorecardSection.delete({ id: sectionToDelete.id })
      console.log('🗑️ Section deleted successfully')
      
      // Remove from local state
      const updatedSections = [...editedScore.sections.items]
      updatedSections.splice(sectionIndex, 1)
      
      // Reorder remaining sections
      updatedSections.forEach((section, index) => {
        section.order = index
      })

      setEditedScore(prev => ({
        ...prev,
        sections: { items: updatedSections }
      }))
      
      // Update the order of remaining sections in the database
      for (const section of updatedSections) {
        await amplifyClient.ScorecardSection.update({
          id: section.id,
          order: section.order
        })
      }
      
      toast.success('Section deleted successfully')
    } catch (error) {
      console.error('❌ Error deleting section:', error)
      toast.error('Failed to delete section: ' + (error instanceof Error ? error.message : 'Unknown error'))
    }
  }

  const handleSave = async () => {
    try {
      console.log('💾 handleSave called with editedScore:', {
        id: editedScore.id,
        name: editedScore.name,
        key: editedScore.key,
        externalId: editedScore.externalId,
        description: editedScore.description,
        sectionsCount: editedScore.sections?.items?.length || 0
      })
      
      // Build update object, converting empty strings to undefined for optional fields
      // DynamoDB/Amplify doesn't like empty strings for optional fields
      const updateData: {
        id: string
        name: string
        key: string
        externalId?: string
        description?: string
      } = {
        id: editedScore.id,
        name: editedScore.name,
        key: editedScore.key
      }
      
      // Only include optional fields if they have actual values
      if (editedScore.externalId && editedScore.externalId.trim() !== '') {
        updateData.externalId = editedScore.externalId
      }
      if (editedScore.description && editedScore.description.trim() !== '') {
        updateData.description = editedScore.description
      }
      
      console.log('💾 Sending scorecard update with data:', updateData)
      
      const result = await amplifyClient.Scorecard.update(updateData)

      console.log('💾 Scorecard update result:', result)
      
      // Check if update actually succeeded
      if (!result.data) {
        console.error('❌ Update returned null data:', result)
        throw new Error('Update failed - no data returned from server')
      }

      // Note: Sections are now saved immediately when created/moved/deleted/renamed
      // This save only handles scorecard-level properties

      // In a future update, we'll save examples to a dedicated table or field
      console.log('Examples would be saved:', editedScore.examples)

      setHasChanges(false)
      toast.success('Scorecard saved successfully')
      console.log('💾 Calling onSave callback...')
      onSave?.()
      console.log('💾 Save complete!')
    } catch (error) {
      console.error('❌ Error saving scorecard:', error)
      toast.error('Failed to save scorecard: ' + (error instanceof Error ? error.message : 'Unknown error'))
    }
  }

  const handleCancel = () => {
    setEditedScore(score)
    setHasChanges(false)
  }

  return (
    <div
      className={cn(
        "w-full rounded-lg text-card-foreground transition-colors relative",
        variant === 'grid' ? (
          isSelected ? "bg-card-selected" : "bg-card hover:bg-accent"
        ) : "bg-card-selected",
        variant === 'detail' && "h-full flex flex-col",
        (isSelected && variant === 'grid') && "selected-border-rounded",
        className
      )}
      {...props}
    >
      <div className={cn(
        "p-4 w-full relative z-10",
        variant === 'detail' && "flex-1 flex flex-col min-h-0"
      )}>
        <div 
          className={cn(
            "w-full",
            variant === 'grid' && "cursor-pointer",
            variant === 'detail' && "h-full flex flex-col min-h-0"
          )}
          onClick={() => variant === 'grid' && onClick?.()}
          role={variant === 'grid' ? "button" : undefined}
          tabIndex={variant === 'grid' ? 0 : undefined}
          onKeyDown={variant === 'grid' ? (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onClick?.()
            }
          } : undefined}
        >
          {variant === 'grid' ? (
            <GridContent score={editedScore} isSelected={isSelected} />
          ) : (
            <DetailContent 
              score={editedScore}
              isFullWidth={isFullWidth}
              onToggleFullWidth={onToggleFullWidth}
              onClose={onClose}
              onViewData={onViewData}
              onFeedbackAnalysis={onFeedbackAnalysis}
              onCostAnalysis={onCostAnalysis}
              onEditChange={handleEditChange}
              onAddSection={handleAddSection}
              onMoveSection={handleMoveSection}
              onDeleteSection={handleDeleteSection}
              onSave={handleSave}
              onCancel={handleCancel}
              hasChanges={hasChanges}
              onScoreSelect={onScoreSelect}
              selectedScoreId={selectedScoreId}
              onCreateItem={onCreateItem}
              onEditItem={onEditItem}
              shouldExpandExamples={shouldExpandExamples}
              onExamplesExpanded={onExamplesExpanded}
              onTaskCreated={onTaskCreated}
              onCreateScore={onCreateScore}
              onOpenGuidelinesEditor={handleOpenGuidelinesEditor}
              onStartInlineEdit={handleStartInlineEdit}
              isGuidelinesEditing={isGuidelinesEditing}
              guidelinesEditValue={guidelinesEditValue}
              hasGuidelinesChanges={hasGuidelinesChanges}
              isSavingGuidelines={isSavingGuidelines}
              onGuidelinesChange={handleGuidelinesChange}
              onSaveGuidelines={handleSaveGuidelines}
              onCancelGuidelinesEdit={handleCancelGuidelinesEdit}
            />
          )}
        </div>
      </div>

      {/* Fullscreen Guidelines Editor */}
      {isGuidelinesFullscreen && (
        <div className="fixed inset-0 z-50 bg-card">
          <div className="flex flex-col h-full p-4">
            {/* Header */}
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-muted-foreground" />
                <h2 className="text-lg font-semibold">Guidelines - {editedScore.name}</h2>
              </div>
              <CardButton
                icon={X}
                onClick={hasGuidelinesChanges ? handleCancelGuidelinesEdit : () => setIsGuidelinesFullscreen(false)}
                aria-label="Close"
              />
            </div>

            {/* Split Editor and Preview - Two rounded rectangles */}
            <div className="flex-1 flex gap-4 overflow-hidden">
              {/* Editor Card */}
              <div className="flex-1 flex flex-col bg-background rounded-lg overflow-hidden">
                <div className="px-4 py-2 bg-card-selected text-sm font-medium text-muted-foreground">
                  Markdown Editor
                </div>
                <div className="flex-1 overflow-hidden">
                  <Editor
                    height="100%"
                    defaultLanguage="markdown"
                    value={guidelinesEditValue}
                    onChange={handleGuidelinesChange}
                    onMount={(editor, monaco) => {
                      // Store editor reference for scroll synchronization
                      editorRef.current = editor
                      
                      // Configure Monaco editor
                      defineCustomMonacoThemes(monaco)
                      applyMonacoTheme(monaco)
                      setupMonacoThemeWatcher(monaco)
                      
                      // Set up scroll synchronization
                      editor.onDidScrollChange(handleEditorScroll)
                    }}
                    options={{
                      ...getCommonMonacoOptions(),
                      wordWrap: 'on',
                      lineNumbers: 'off',
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      fontSize: 14,
                      tabSize: 2,
                      insertSpaces: true,
                      automaticLayout: true,
                    }}
                  />
                </div>
              </div>

              {/* Preview Card */}
              <div className="flex-1 flex flex-col bg-background rounded-lg overflow-hidden">
                <div className="px-4 py-2 bg-card-selected text-sm font-medium text-muted-foreground">
                  Preview
                </div>
                <div ref={previewRef} className="flex-1 overflow-y-auto p-4">
                  {guidelinesEditValue ? (
                    <div className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-muted-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkBreaks]}
                        components={{
                          // Customize components for better styling
                          p: ({ children }) => <p className="mb-2 last:mb-0 text-sm">{children}</p>,
                          ul: ({ children }) => <ul className="mb-2 ml-4 list-disc">{children}</ul>,
                          ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal">{children}</ol>,
                          li: ({ children }) => <li className="mb-1">{children}</li>,
                          strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                          em: ({ children }) => <em className="italic">{children}</em>,
                          code: ({ children }) => <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                          pre: ({ children }) => <pre className="bg-muted p-2 rounded overflow-x-auto text-xs">{children}</pre>,
                          h1: ({ children }) => <h1 className="text-base font-semibold mb-2 text-foreground">{children}</h1>,
                          h2: ({ children }) => <h2 className="text-sm font-semibold mb-2 text-foreground">{children}</h2>,
                          h3: ({ children }) => <h3 className="text-sm font-medium mb-1 text-foreground">{children}</h3>,
                        }}
                      >
                        {guidelinesEditValue}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                      Start typing to see preview...
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer with save/cancel buttons if changes exist */}
            {hasGuidelinesChanges && (
              <div className="flex justify-end items-center gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={handleCancelGuidelinesEdit}
                  disabled={isSavingGuidelines}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleSaveGuidelines}
                  disabled={isSavingGuidelines}
                >
                  {isSavingGuidelines ? (
                    <>
                      <div className="animate-spin h-4 w-4 border-2 border-background border-t-transparent rounded-full mr-2" />
                      Saving Guidelines...
                    </>
                  ) : (
                    'Save Guidelines'
                  )}
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fullscreen Guidelines Editor */}
      <FullscreenGuidelinesEditor
        isOpen={isGuidelinesFullscreen}
        title={`Guidelines - ${editedScore.name}`}
        value={guidelinesEditValue}
        onChange={handleGuidelinesChange}
        onSave={handleSaveGuidelines}
        onCancel={handleCancelGuidelinesEdit}
        hasChanges={hasGuidelinesChanges}
        isSaving={isSavingGuidelines}
      />
    </div>
  )
} 
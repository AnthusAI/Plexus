import * as React from 'react'
import { Card } from '@/components/ui/card'
import { MoreHorizontal, Pencil, Database, ListChecks, X, Square, Columns2, Plus, ChevronUp, ChevronDown, ListCheck, ChevronRight, FileText, Key, StickyNote, Edit, IdCard, TestTube } from 'lucide-react'
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

export interface ScorecardData {
  id: string
  name: string
  key: string
  description: string
  type: string
  order: number
  externalId?: string
  scoreCount?: number
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
}

const GridContent = React.memo(({ 
  score,
  isSelected 
}: { 
  score: ScorecardData
  isSelected?: boolean
}) => {
  const scoreCount = score.scoreCount || 0
  const scoreText = scoreCount === 1 ? 'Score' : 'Scores'

  return (
    <div className="flex justify-between items-start w-full">
      <div className="space-y-1.5">
        <div className="font-medium">{score.name}</div>
        <div className="text-sm text-muted-foreground flex items-center gap-1">
          <IdCard className="h-3 w-3" />
          <span>{score.externalId || '-'}</span>
        </div>
        <div className="text-sm text-muted-foreground">{scoreCount} {scoreText}</div>
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
}

export const DetailContent = React.memo(function DetailContent({
  score,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  onViewData,
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
  onExamplesExpanded
}: DetailContentProps) {
  const { selectedAccount } = useAccount()
  const [sectionNameChanges, setSectionNameChanges] = React.useState<Record<string, string>>({})
  const [isExamplesExpanded, setIsExamplesExpanded] = React.useState(false)
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

  const handleTestItemWithScore = (scoreId: string) => {
    console.log('Testing item with score:', { itemId: testItemDialog.itemId, scoreId });
    // TODO: Implement actual test logic
    toast.success(`Testing item "${testItemDialog.displayValue}" with selected score`);
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
      <div className="flex justify-between items-start w-full">
        <div className="space-y-2 flex-1">
          <div className="flex items-center gap-2 mb-3">
            <ListChecks className="h-5 w-5 text-foreground" />
            <span className="text-lg font-semibold">Scorecard</span>
          </div>
          <Input
            value={score.name}
            onChange={(e) => onEditChange?.({ name: e.target.value })}
            className="text-lg font-semibold bg-background border-0 px-2 h-auto w-full
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="Scorecard Name"
          />
          <div className="flex gap-4 w-full">
            <Input
              value={score.key}
              onChange={(e) => onEditChange?.({ key: e.target.value })}
              className="font-mono bg-background border-0 px-2 h-auto flex-1
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground rounded-md"
              placeholder="scorecard-key"
            />
            <Input
              value={score.externalId ?? ''}
              onChange={(e) => onEditChange?.({ externalId: e.target.value })}
              className="font-mono bg-background border-0 px-2 h-auto flex-1
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground rounded-md"
              placeholder="External ID"
            />
          </div>
          <p className="text-sm text-muted-foreground">{score.description}</p>
        </div>
        <div className="flex gap-2 ml-4">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <CardButton
                icon={MoreHorizontal}
                onClick={() => {}}
                aria-label="More options"
              />
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content align="end" className="min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
                {onViewData && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={onViewData}
                  >
                    <Database className="mr-2 h-4 w-4" />
                    View Data
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

      {hasChanges && (
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={onSave}>Save Changes</Button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto mt-6 w-full">
        <div className="space-y-6 w-full">
          <div>
            <div className="flex justify-between items-center mb-2">
              <div className="flex items-center">
                <h3 
                  className="text-lg font-semibold cursor-pointer flex items-center"
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
                  <DropdownMenu.Content align="end" className="min-w-[300px] overflow-hidden rounded-md border bg-popover p-2 text-popover-foreground shadow-md">
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

          {score.sections?.items?.map((section, index) => {
            // Process scores for this section
            const processedScores = section.scores?.items?.map((score) => ({
              id: score.id,
              name: score.name,
              description: score.description || '',
              type: score.type,
              order: score.order,
              key: score.key || '',
              icon: <ListCheck className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
            })) || [];
            
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
                      onClick={() => {}}
                    />
                  </div>
                </div>
                <div className="bg-background rounded-lg w-full">
                  <div className="@container w-full p-4">
                    <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-4 w-full">
                      {processedScores.map((scoreData) => (
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
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
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
  className, 
  ...props 
}: ScorecardComponentProps) {
  const [editedScore, setEditedScore] = React.useState<ScorecardData>(score)
  const [hasChanges, setHasChanges] = React.useState(false)

  React.useEffect(() => {
    setEditedScore(score)
  }, [score])

  const handleEditChange = (changes: Partial<ScorecardData>) => {
    setEditedScore(prev => {
      const updated = { ...prev, ...changes }
      // Only set hasChanges if name, key, or externalId were changed
      if ('name' in changes || 'key' in changes || 'externalId' in changes || 'examples' in changes) {
        setHasChanges(true)
      }
      return updated
    })
  }

  const handleAddSection = () => {
    const maxOrder = Math.max(0, ...(editedScore.sections?.items || []).map(s => s.order))
    const newSection = {
      id: `temp_${Date.now()}`,
      name: "New section",
      order: maxOrder + 1,
      scores: { items: [] }
    }
    setEditedScore(prev => ({
      ...prev,
      sections: {
        items: [...(prev.sections?.items || []), newSection]
      }
    }))
  }

  const handleMoveSection = (index: number, direction: 'up' | 'down') => {
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
  }

  const handleDeleteSection = (sectionIndex: number) => {
    if (!editedScore.sections?.items) return

    const updatedSections = [...editedScore.sections.items]
    updatedSections.splice(sectionIndex, 1)
    updatedSections.forEach((section, index) => {
      section.order = index
    })

    setEditedScore(prev => ({
      ...prev,
      sections: { items: updatedSections }
    }))
  }

  const handleSave = async () => {
    try {
      // For now, we'll just save the basic properties
      // We'll need to add a separate API or update the schema to handle examples
      await amplifyClient.Scorecard.update({
        id: editedScore.id,
        name: editedScore.name,
        key: editedScore.key,
        externalId: editedScore.externalId,
        description: editedScore.description
      })

      // In a future update, we'll save examples to a dedicated table or field
      console.log('Examples would be saved:', editedScore.examples)

      setHasChanges(false)
      onSave?.()
    } catch (error) {
      console.error('Error saving scorecard:', error)
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
            />
          )}
        </div>
      </div>
    </div>
  )
} 
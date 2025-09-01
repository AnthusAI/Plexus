"use client"
import React, { useState, useEffect, useCallback, useRef } from "react"
import { useRouter, usePathname, useParams } from "next/navigation"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Button } from "@/components/ui/button"
import { Plus, Waypoints, FileText, Shrink, BookOpenCheck } from "lucide-react"
import { toast } from "sonner"
import ProcedureTask, { ProcedureTaskData } from "@/components/ProcedureTask"
import ProcedureDetail from "@/components/procedure-detail"
import ProcedureConversationViewer from "@/components/procedure-conversation-viewer"
import ScorecardContext from "@/components/ScorecardContext"
import TemplateSelector from "@/components/template-selector"
import { motion, AnimatePresence } from "framer-motion"
import { useMediaQuery } from "@/hooks/use-media-query"
import { useAccount } from '@/app/contexts/AccountContext'
import { observeTaskUpdates, observeTaskStageUpdates, observeGraphNodeUpdates } from "@/utils/subscriptions"

type Procedure = Schema['Procedure']['type']
type Task = Schema['Task']['type']
type ProcedureWithTask = Procedure & {
  task?: Task | null
}

const client = generateClient<Schema>()

interface ProceduresDashboardProps {
  initialSelectedProcedureId?: string | null
}

function ProceduresDashboard({ initialSelectedProcedureId }: ProceduresDashboardProps = {}) {
  const router = useRouter()
  const pathname = usePathname()
  const params = useParams()
  const { selectedAccount } = useAccount()
  
  // Extract procedure ID from URL params if present, or use the prop
  const procedureIdFromParams = (params && 'id' in params) ? params.id as string : null
  const finalInitialProcedureId = initialSelectedProcedureId || procedureIdFromParams
  
  const [procedures, setProcedures] = useState<ProcedureWithTask[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedProcedureId, setSelectedProcedureId] = useState<string | null>(finalInitialProcedureId)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [isEditMode, setIsEditMode] = useState(false)
  const [showTemplateSelector, setShowTemplateSelector] = useState(false)
  const [isConversationFullscreen, setIsConversationFullscreen] = useState(false)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const lastLoadTimeRef = useRef(0)

  // All hooks must be at the top before any conditional returns
  const handleSelectProcedure = useCallback((id: string | null) => {
    setSelectedProcedureId(id)
    // Update URL without causing full rerender
    const newPathname = id ? `/lab/procedures/${id}` : '/lab/procedures'
    window.history.pushState(null, '', newPathname)
    
    if (isNarrowViewport && id) {
      setIsFullWidth(true)
    }
  }, [isNarrowViewport])

  const handleCloseProcedure = useCallback(() => {
    setSelectedProcedureId(null)
    setIsFullWidth(false)
    setIsEditMode(false)
    
    // Update URL without triggering a navigation/re-render
    window.history.pushState(null, '', '/lab/procedures')
  }, [])

  // Memoize click handler - moved to top with other hooks
  const getProcedureClickHandler = useCallback((procedureId: string) => {
    return (e?: React.MouseEvent | React.SyntheticEvent | any) => {
      if (e && typeof e.preventDefault === 'function') {
        e.preventDefault()
      }
      setIsFullWidth(false)
      try { (document.activeElement as HTMLElement | null)?.blur?.() } catch {}
      handleSelectProcedure(procedureId)
    }
  }, [handleSelectProcedure])

  const loadProcedures = useCallback(async (force = false) => {
    if (!selectedAccount?.id) {
      setProcedures([])
      setIsLoading(false)
      return
    }

    try {
      setIsLoading(true)
      lastLoadTimeRef.current = Date.now()
      console.log('Loading procedures for account:', selectedAccount.id)
      // First get procedures
      const proceduresResult = await client.graphql({
        query: `
          query ListProcedureByAccountIdAndUpdatedAt(
            $accountId: String!
            $sortDirection: ModelSortDirection
            $limit: Int
          ) {
            listProcedureByAccountIdAndUpdatedAt(
              accountId: $accountId
              sortDirection: $sortDirection
              limit: $limit
            ) {
              items {
                id
                featured
                templateId
                code
                rootNodeId
                createdAt
                updatedAt
                accountId
                scorecardId
                scorecard {
                  id
                  name
                }
                scoreId
                score {
                  id
                  name
                }

              }
              nextToken
            }
          }
        `,
        variables: {
          accountId: selectedAccount.id,
          sortDirection: 'DESC',
          limit: 1000
        }
      })
      console.log('Raw procedure query result:', proceduresResult)
      const proceduresData = (proceduresResult as any).data?.listProcedureByAccountIdAndUpdatedAt?.items || []
      
      // Then get tasks related to procedures (via metadata)
      const tasksResult = await client.graphql({
        query: `
          query ListTaskByAccountIdAndUpdatedAt(
            $accountId: String!
            $sortDirection: ModelSortDirection
            $limit: Int
          ) {
            listTaskByAccountIdAndUpdatedAt(
              accountId: $accountId
              sortDirection: $sortDirection
              limit: $limit
            ) {
              items {
                id
                type
                status
                target
                command
                description
                dispatchStatus
                metadata
                createdAt
                startedAt
                completedAt
                estimatedCompletionAt
                errorMessage
                errorDetails
                currentStageId
                stages {
                  items {
                    id
                    name
                    order
                    status
                    statusMessage
                    startedAt
                    completedAt
                    estimatedCompletionAt
                    processedItems
                    totalItems
                  }
                }
              }
            }
          }
        `,
        variables: {
          accountId: selectedAccount.id,
          sortDirection: 'DESC',
          limit: 1000
        }
      })
      
      console.log('Raw tasks query result:', tasksResult)
      const allTasks = (tasksResult as any).data?.listTaskByAccountIdAndUpdatedAt?.items || []
      
      // Filter tasks that have procedure_id in metadata
      const procedureTasks = allTasks.filter((task: Task) => {
        try {
          const metadata = typeof task.metadata === 'string' ? JSON.parse(task.metadata) : task.metadata
          return metadata && metadata.procedure_id
        } catch {
          return false
        }
      })
      
      // Create a map of procedure_id -> task for quick lookup
      const procedureTaskMap = new Map()
      procedureTasks.forEach((task: Task) => {
        try {
          const metadata = typeof task.metadata === 'string' ? JSON.parse(task.metadata) : task.metadata
          if (metadata && metadata.procedure_id) {
            procedureTaskMap.set(metadata.procedure_id, task)
          }
        } catch {
          // Ignore parsing errors
        }
      })
      
      // Combine procedures with their tasks
      const data = proceduresData.map((procedure: Procedure): ProcedureWithTask => ({
        ...procedure,
        task: procedureTaskMap.get(procedure.id) || null
      }))
      console.log('Procedures data from query:', data)
      
      // Check if we're looking for a specific procedure (for debugging)
      if (force) {
        console.log('Forced reload - checking if we can find recently created procedures...')
        const recentProcedures = data?.slice(0, 5)?.map((proc: Procedure) => ({
          id: proc.id,
          createdAt: proc.createdAt
        }))
        console.log('Most recent 5 procedures by API order:', recentProcedures)
      }
      
      // Sort procedures in reverse chronological order (newest first)
      const sortedData = data?.sort((a: Procedure, b: Procedure) => {
        const dateA = new Date(a.updatedAt || a.createdAt)
        const dateB = new Date(b.updatedAt || b.createdAt)
        return dateB.getTime() - dateA.getTime()
      }) || []
      console.log('Sorted procedures data:', sortedData)
      
      // Only update state if data has actually changed
      setProcedures(prevProcedures => {
        console.log('Previous procedures:', prevProcedures.length, 'items')
        console.log('New procedures:', sortedData.length, 'items')
        
        // Quick comparison: check length first
        if (prevProcedures.length !== sortedData.length) {
          console.log('Length changed, updating procedures list')
          return sortedData
        }
        
        // If same length, check if all IDs match in same order
        const hasChanges = prevProcedures.some((prev, index) => {
          const current = sortedData[index]
          return !current || prev.id !== current.id || prev.updatedAt !== current.updatedAt
        })
        
        if (hasChanges) {
          console.log('Procedures data changed, updating list')
          return sortedData
        } else {
          console.log('No changes detected, keeping previous data')
          return prevProcedures
        }
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load procedures')
    } finally {
      setIsLoading(false)
    }
  }, [selectedAccount?.id])

  useEffect(() => {
    loadProcedures()
  }, [loadProcedures])

  // Task monitoring with real-time subscriptions for procedure tasks
  useEffect(() => {
    console.log('Setting up task subscriptions for procedures')

    const taskSubscription = observeTaskUpdates().subscribe({
      next: (value: any) => {
        const { type, data } = value;
        console.log(`Task ${type} update for procedures:`, data);
        
        // Check if this is a procedure task by looking for procedure_id in metadata
        if (data?.metadata) {
          try {
            const metadata = typeof data.metadata === 'string' ? JSON.parse(data.metadata) : data.metadata;
            if (metadata?.procedure_id) {
              console.log(`Updating procedure ${metadata.procedure_id} with task data:`, data);
              
              // Update the procedures list with new task data
              setProcedures(prevProcedures => 
                prevProcedures.map(procedure => 
                  procedure.id === metadata.procedure_id 
                    ? { ...procedure, task: data }
                    : procedure
                )
              );
            }
          } catch (error) {
            console.error('Error parsing task metadata:', error);
          }
        }
      },
      error: (error: any) => {
        console.error('Task subscription error:', error);
      }
    });

    const stageSubscription = observeTaskStageUpdates().subscribe({
      next: (value: any) => {
        const { type, data } = value;
        console.log(`TaskStage ${type} update for procedures:`, data);
        
        if (data?.taskId) {
          // Update the procedures list with new stage data
          setProcedures(prevProcedures => 
            prevProcedures.map((procedure: ProcedureWithTask) => {
              if (procedure.task?.id === data.taskId) {
                console.log(`Updating procedure ${procedure.id} stages with:`, data);
                
                // Handle LazyLoader for stages - access synchronously if available
                const currentStages = procedure.task?.stages as any;
                const updatedStages = currentStages?.items ? [...currentStages.items] : [];
                const existingStageIndex = updatedStages.findIndex((stage: any) => stage.id === data.id);
                
                if (existingStageIndex >= 0) {
                  updatedStages[existingStageIndex] = { ...updatedStages[existingStageIndex], ...data };
                } else {
                  updatedStages.push(data);
                }
                
                const updatedTask = {
                  ...procedure.task!,
                  stages: currentStages ? {
                    ...currentStages,
                    items: updatedStages.sort((a: any, b: any) => a.order - b.order)
                  } : { items: updatedStages.sort((a: any, b: any) => a.order - b.order) },
                  currentStageId: data.status === 'RUNNING' ? data.name : procedure.task?.currentStageId
                };

                console.log('Updated procedure task with stages:', {
                  procedureId: procedure.id,
                  taskId: updatedTask.id,
                  stagesCount: updatedTask.stages?.items?.length,
                  currentStageId: updatedTask.currentStageId
                });

                return { ...procedure, task: updatedTask };
              }
              return procedure;
            })
          );
        }
      },
      error: (error: any) => {
        console.error('TaskStage subscription error:', error);
      }
    });

    return () => {
      console.log('Cleaning up task subscriptions for procedures');
      taskSubscription.unsubscribe();
      stageSubscription.unsubscribe();
    };
  }, []); // Empty dependency array since we want this to run once

  const handleEditProcedure = useCallback((procedureId: string) => {
    console.log('Edit procedure:', procedureId)
    setIsEditMode(true)
  }, [])

  const handleDuplicateProcedure = useCallback(async (procedureId: string) => {
    console.log('handleDuplicateProcedure called with:', procedureId)
    try {
      const procedure = procedures.find(proc => proc.id === procedureId)
      console.log('Found procedure:', procedure)
      if (!procedure) {
        toast.error('Procedure not found')
        return
      }

      console.log('Creating duplicate procedure...')
      console.log('Selected account:', selectedAccount?.id)
      
      if (!selectedAccount?.id) {
        toast.error('No account selected')
        return
      }
      
      // Since procedures don't have names, we'll need to create a description
      // that indicates it's a duplicate. For now, let's just duplicate it as-is
      const { data: newProcedure } = await (client.models.Procedure.create as any)({
        featured: procedure.featured || false,
        templateId: procedure.templateId || null,
        code: procedure.code || null, // Copy the code if it exists
        rootNodeId: null, // Will be set after creating nodes
        scorecardId: procedure.scorecardId,
        scoreId: procedure.scoreId,
        accountId: selectedAccount.id,
      })

      console.log('New procedure created:', newProcedure)
      if (newProcedure) {
        // TODO: Copy the procedure nodes and versions from the original
        // For now, just refresh the procedures list
        await loadProcedures(true) // Force reload to ensure duplicate appears
        // Select the newly created duplicate procedure
        handleSelectProcedure(newProcedure.id)
        toast.success('Procedure duplicated successfully')
      }
    } catch (error) {
      console.error('Error duplicating procedure:', error)
      toast.error('Failed to duplicate procedure')
    }
  }, [procedures, loadProcedures, handleSelectProcedure, selectedAccount])

  // Handle URL synchronization for browser back/forward navigation
  useEffect(() => {
    const syncFromUrl = () => {
      const procedureMatch = window.location.pathname.match(/\/lab\/procedures\/([^\/]+)/)
      const idFromUrl = procedureMatch ? (procedureMatch[1] as string) : null
      // Only sync on back/forward, not on programmatic changes immediately after click
      setSelectedProcedureId(prev => prev === idFromUrl ? prev : idFromUrl)
    }
    
    // Listen for browser back/forward navigation
    window.addEventListener('popstate', syncFromUrl)
    return () => window.removeEventListener('popstate', syncFromUrl)
  }, [])

  // Focus handler disabled to prevent unwanted reloads when returning to browser
  // Data will refresh naturally through other user interactions or manual refresh

  const handleCreateProcedure = () => {
    setShowTemplateSelector(true)
  }

  const handleCreateProcedureFromTemplate = async (template: Schema['ProcedureTemplate']['type']) => {
    if (!selectedAccount?.id) {
      toast.error('No account selected')
      return
    }

    try {
      console.log('Creating procedure from template:', { 
        templateId: template.id, 
        templateName: template.name,
        templateCode: template.template?.substring(0, 100) + '...'
      })
      
      // Create procedure with template reference and copy template code
      const createInput = {
        featured: false,
        templateId: template.id,
        code: template.template, // Copy template YAML code to procedure
        rootNodeId: null, // Will be set when nodes are created
        scorecardId: selectedScorecard || null,
        scoreId: selectedScore || null,
        accountId: selectedAccount.id,
      }
      
      console.log('Create input:', createInput)
      
      const result = await (client.models.Procedure.create as any)(createInput as any)
      const { data: newProcedure, errors } = result

      if (errors && errors.length > 0) {
        console.error('GraphQL errors creating procedure:', errors)
        toast.error('Failed to create procedure: ' + errors.map((e: any) => e.message).join(', '))
        return
      }

      if (newProcedure) {
        console.log('Procedure created successfully:', newProcedure)
        // Refresh procedures list and select the new procedure
        console.log('About to reload procedures for newly created procedure:', newProcedure.id)
        await loadProcedures(true) // Force reload to ensure new procedure appears
        console.log('Finished reloading procedures')
        handleSelectProcedure(newProcedure.id)
        // Close template selector
        setShowTemplateSelector(false)
        toast.success(`Procedure created from template "${template.name}"`)
      } else {
        console.error('No procedure data returned')
        toast.error('Failed to create procedure: No data returned')
      }
    } catch (error) {
      console.error('Error creating procedure from template:', error)
      toast.error('Failed to create procedure from template')
    }
  }

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.pageX
    const startWidth = leftPanelWidth

    const handleDrag = (e: MouseEvent) => {
      const delta = e.pageX - startX
      const newWidth = Math.min(Math.max(startWidth + (delta / window.innerWidth) * 100, 20), 80)
      setLeftPanelWidth(newWidth)
    }

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleDragEnd)
    }

    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleDragEnd)
  }

  const handleDelete = async (procedureId: string) => {
    try {
      await (client.models.Procedure.delete as any)({ id: procedureId })
      setProcedures(prev => prev.filter(proc => proc.id !== procedureId))
      if (selectedProcedureId === procedureId) {
        setSelectedProcedureId(null)
        setIsEditMode(false)
        // Update URL when deleting the currently selected procedure
        window.history.pushState(null, '', '/lab/procedures')
      }
      toast.success('Procedure deleted successfully')
    } catch (error) {
      console.error('Error deleting procedure:', error)
      toast.error('Failed to delete procedure')
    }
  }

  // Transform procedures to ProcedureTaskData - memoized to prevent unnecessary re-renders
  const transformProcedure = useCallback((procedure: ProcedureWithTask): ProcedureTaskData => ({
    id: procedure.id,
    title: `${procedure.scorecard?.name || 'Procedure'} - ${procedure.score?.name || 'Score'}`,
    featured: procedure.featured || false,
    rootNodeId: procedure.rootNodeId || undefined,
    createdAt: procedure.createdAt,
    updatedAt: procedure.updatedAt,
    scorecard: procedure.scorecard ? { name: procedure.scorecard.name } : null,
    score: procedure.score ? { name: procedure.score.name } : null,
    task: procedure.task ? {
      id: procedure.task.id,
      type: procedure.task.type || 'Procedure',
      status: procedure.task.status || 'PENDING',
      target: procedure.task.target || '',
      command: procedure.task.command || '',
      description: procedure.task.description || undefined,
      dispatchStatus: procedure.task.dispatchStatus || undefined,
      metadata: typeof procedure.task.metadata === 'string' ? procedure.task.metadata : JSON.stringify(procedure.task.metadata),
      createdAt: procedure.task.createdAt || undefined,
      startedAt: procedure.task.startedAt || undefined,
      completedAt: procedure.task.completedAt || undefined,
      estimatedCompletionAt: procedure.task.estimatedCompletionAt || undefined,
      errorMessage: procedure.task.errorMessage || undefined,
      errorDetails: typeof procedure.task.errorDetails === 'string' ? procedure.task.errorDetails : JSON.stringify(procedure.task.errorDetails) || undefined,
      currentStageId: procedure.task.currentStageId || undefined,
      stages: procedure.task.stages ? {
        items: (procedure.task.stages as any)?.items || []
      } : undefined
    } : undefined
  }), [])
  

  // Loading and error states
  if (isLoading || error) {
    return (
      <div className="@container flex flex-col h-full p-3 overflow-hidden">
        <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
          <div className="@[600px]:flex-grow w-full">
            <ScorecardContext 
              selectedScorecard={selectedScorecard}
              setSelectedScorecard={setSelectedScorecard}
              selectedScore={selectedScore}
              setSelectedScore={setSelectedScore}
              skeletonMode={isLoading}
            />
          </div>
          <div className="flex-shrink-0">
            <Button onClick={handleCreateProcedure} disabled={isLoading}>
              <Plus className="h-4 w-4 mr-2" />
              New Procedure
            </Button>
          </div>
        </div>
        
        {error ? (
          <div className="text-center text-destructive p-8">
            <p>Error loading procedures: {error}</p>
          </div>
        ) : (
          <div className="animate-pulse space-y-4">
            <div className="h-32 bg-gray-200 rounded"></div>
            <div className="h-32 bg-gray-200 rounded"></div>
            <div className="h-32 bg-gray-200 rounded"></div>
          </div>
        )}
      </div>
    )
  }


  // Render selected procedure detail or edit form
  const renderSelectedProcedure = () => {
    if (!selectedProcedureId) return null
    const procedure = procedures.find(proc => proc.id === selectedProcedureId)
    if (!procedure) return null

    // If in edit mode, render the edit form instead of the detail view
    if (isEditMode) {
      return (
        <ProcedureDetail 
          procedureId={selectedProcedureId}
          initialEditMode={true}
          onSave={() => {
            // Exit edit mode and refresh procedures list after save
            setIsEditMode(false)
            // Reload procedures to get updated data
            loadProcedures(true)
          }}
          onCancel={() => {
            // Exit edit mode without saving
            setIsEditMode(false)
          }}
        />
      )
    }

    return (
      <ProcedureTask
        variant="detail"
        procedure={transformProcedure(procedure)}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={handleCloseProcedure}
        onDelete={handleDelete}
        onEdit={handleEditProcedure}
        onDuplicate={handleDuplicateProcedure}
        onConversationFullscreenChange={setIsConversationFullscreen}
      />
    )
  }

  return (
    <div className="@container flex flex-col h-full p-3 overflow-hidden">
      {/* Fixed header */}
      <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
        <div className="@[600px]:flex-grow w-full">
          <ScorecardContext 
            selectedScorecard={selectedScorecard}
            setSelectedScorecard={setSelectedScorecard}
            selectedScore={selectedScore}
            setSelectedScore={setSelectedScore}
          />
        </div>
        <div className="flex-shrink-0">
          <Button onClick={handleCreateProcedure}>
            <Plus className="h-4 w-4 mr-2" />
            Create
          </Button>
        </div>
      </div>

      {/* Procedures Content */}
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <AnimatePresence mode="popLayout">
          <motion.div 
            key="procedures-layout"
            className="flex flex-1 min-h-0"
            layout
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ 
              type: "spring", 
              stiffness: 300, 
              damping: 30,
              opacity: { duration: 0.2 }
            }}
          >
            {/* Left panel - grid content */}
            <motion.div 
              className={`${selectedProcedureId && !isNarrowViewport && isFullWidth ? 'hidden' : 'flex-1'} h-full overflow-auto`}
              style={selectedProcedureId && !isNarrowViewport && !isFullWidth ? {
                width: `${leftPanelWidth}%`
              } : undefined}
              layout
              transition={{ 
                type: "spring", 
                stiffness: 300, 
                damping: 30 
              }}
            >
              <div className="@container space-y-3 overflow-visible">
                {procedures.length === 0 && isLoading ? (
                  <div className="animate-pulse space-y-4">
                    <div className="h-32 bg-gray-200 rounded"></div>
                    <div className="h-32 bg-gray-200 rounded"></div>
                    <div className="h-32 bg-gray-200 rounded"></div>
                  </div>
                ) : (
                  <div className={`
                    grid gap-3
                    ${selectedProcedureId && !isNarrowViewport && !isFullWidth ? 'grid-cols-1' : 'grid-cols-1 @[640px]:grid-cols-2'}
                  `}>
                    {procedures.map((procedure) => {
                      const clickHandler = getProcedureClickHandler(procedure.id)
                      
                      return (
                        <div 
                          key={procedure.id}
                          role="button"
                          tabIndex={0}
                          onClick={clickHandler}
                          onKeyDown={(ev) => {
                            if (ev.key === 'Enter' || ev.key === ' ') {
                              ev.preventDefault()
                              clickHandler()
                            }
                          }}
                          aria-pressed={procedure.id === selectedProcedureId}
                          data-selected={procedure.id === selectedProcedureId ? 'true' : 'false'}
                        >
                          <ProcedureTask
                            variant="grid"
                            procedure={transformProcedure(procedure)}
                            onClick={clickHandler}
                            isSelected={procedure.id === selectedProcedureId}
                            onDelete={handleDelete}
                            onEdit={handleEditProcedure}
                            onDuplicate={handleDuplicateProcedure}
                          />
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </motion.div>

            {/* Divider for split view */}
            {selectedProcedureId && !isNarrowViewport && !isFullWidth && (
              <div
                className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
                onMouseDown={handleDragStart}
              >
                <div className="absolute inset-0 rounded-full transition-colors duration-150 
                  group-hover:bg-accent" />
              </div>
            )}

            {/* Right panel - procedure detail view */}
            <AnimatePresence>
              {selectedProcedureId && !isNarrowViewport && !isFullWidth && !isConversationFullscreen && (
                <motion.div 
                  key={`procedure-detail-${selectedProcedureId}`}
                  className="h-full overflow-hidden flex-shrink-0"
                  style={{ width: `${100 - leftPanelWidth}%` }}
                  initial={{ width: 0, opacity: 0 }}
                  animate={{ 
                    width: `${100 - leftPanelWidth}%`, 
                    opacity: 1 
                  }}
                  exit={{ 
                    width: 0, 
                    opacity: 0 
                  }}
                  transition={{ 
                    type: "spring", 
                    stiffness: 300, 
                    damping: 30 
                  }}
                >
                  {renderSelectedProcedure()}
                </motion.div>
              )}
            </AnimatePresence>

          </motion.div>
        </AnimatePresence>
        
        {/* Full-screen view for mobile or full-width mode */}
        {selectedProcedureId && (isNarrowViewport || isFullWidth) && !isConversationFullscreen && (
          <div className="fixed inset-0 z-50 overflow-y-auto">
            {renderSelectedProcedure()}
          </div>
        )}
        
        {/* Conversation full-screen view - renders when conversation is fullscreen */}
        {selectedProcedureId && isConversationFullscreen && (
          <div className="fixed inset-0 z-50 overflow-y-auto bg-background">
            <div className="w-full h-screen bg-background py-6 px-3 overflow-y-auto flex flex-col">
              <div className="flex items-center justify-between mb-4 flex-shrink-0 px-3">
                <h3 className="text-lg font-semibold flex items-center gap-2 text-muted-foreground">
                  <BookOpenCheck className="h-5 w-5" />
                  Procedures
                </h3>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                  onClick={() => setIsConversationFullscreen(false)}
                  aria-label="Exit fullscreen"
                >
                  <Shrink className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto">
                <ProcedureConversationViewer 
                  procedureId={selectedProcedureId} 
                  onSessionCountChange={() => {}} // We don't need to track session count here
                  isFullscreen={true}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Template Selector Modal */}
      {selectedAccount && (
        <TemplateSelector
          accountId={selectedAccount.id}
          open={showTemplateSelector}
          onOpenChange={setShowTemplateSelector}
          onTemplateSelect={handleCreateProcedureFromTemplate}
        />
      )}
    </div>
  )
}

// Memoize the component to prevent unnecessary re-renders from parent
export default React.memo(ProceduresDashboard)

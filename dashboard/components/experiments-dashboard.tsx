"use client"
import React, { useState, useEffect, useCallback, useRef } from "react"
import { useRouter, usePathname, useParams } from "next/navigation"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Button } from "@/components/ui/button"
import { Plus, Waypoints } from "lucide-react"
import { toast } from "sonner"
import ExperimentTask, { ExperimentTaskData } from "@/components/ExperimentTask"
import ExperimentDetail from "@/components/experiment-detail"
import ScorecardContext from "@/components/ScorecardContext"
import TemplateSelector from "@/components/template-selector"
import { motion, AnimatePresence } from "framer-motion"
import { useMediaQuery } from "@/hooks/use-media-query"
import { useAccount } from '@/app/contexts/AccountContext'

type Experiment = Schema['Experiment']['type']

const client = generateClient<Schema>()

interface ExperimentsDashboardProps {
  initialSelectedExperimentId?: string | null
}

function ExperimentsDashboard({ initialSelectedExperimentId }: ExperimentsDashboardProps = {}) {
  const router = useRouter()
  const pathname = usePathname()
  const params = useParams()
  const { selectedAccount } = useAccount()
  
  // Extract experiment ID from URL params if present, or use the prop
  const experimentIdFromParams = (params && 'id' in params) ? params.id as string : null
  const finalInitialExperimentId = initialSelectedExperimentId || experimentIdFromParams
  
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedExperimentId, setSelectedExperimentId] = useState<string | null>(finalInitialExperimentId)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [isEditMode, setIsEditMode] = useState(false)
  const [showTemplateSelector, setShowTemplateSelector] = useState(false)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const lastLoadTimeRef = useRef(0)

  // All hooks must be at the top before any conditional returns
  const handleSelectExperiment = useCallback((id: string | null) => {
    setSelectedExperimentId(id)
    // Update URL without causing full rerender
    const newPathname = id ? `/lab/experiments/${id}` : '/lab/experiments'
    window.history.pushState(null, '', newPathname)
    
    if (isNarrowViewport && id) {
      setIsFullWidth(true)
    }
  }, [isNarrowViewport])

  const handleCloseExperiment = useCallback(() => {
    setSelectedExperimentId(null)
    setIsFullWidth(false)
    setIsEditMode(false)
    
    // Update URL without triggering a navigation/re-render
    window.history.pushState(null, '', '/lab/experiments')
  }, [])

  // Memoize click handler - moved to top with other hooks
  const getExperimentClickHandler = useCallback((experimentId: string) => {
    return (e?: React.MouseEvent | React.SyntheticEvent | any) => {
      if (e && typeof e.preventDefault === 'function') {
        e.preventDefault()
      }
      setIsFullWidth(false)
      try { (document.activeElement as HTMLElement | null)?.blur?.() } catch {}
      handleSelectExperiment(experimentId)
    }
  }, [handleSelectExperiment])

  const loadExperiments = useCallback(async (force = false) => {
    if (!selectedAccount?.id) {
      setExperiments([])
      setIsLoading(false)
      return
    }

    try {
      setIsLoading(true)
      lastLoadTimeRef.current = Date.now()
      console.log('Loading experiments for account:', selectedAccount.id)
      const result = await (client.models.Experiment.listExperimentByAccountIdAndUpdatedAt as any)({
        accountId: selectedAccount.id,
        limit: 1000 // Increase limit to get more experiments
      })
      console.log('Raw experiment query result:', result)
      const { data } = result
      console.log('Experiments data from query:', data)
      
      // Check if we're looking for a specific experiment (for debugging)
      if (force) {
        console.log('Forced reload - checking if we can find recently created experiments...')
        const recentExperiments = data?.slice(0, 5)?.map((exp: Experiment) => ({
          id: exp.id,
          createdAt: exp.createdAt
        }))
        console.log('Most recent 5 experiments by API order:', recentExperiments)
      }
      
      // Sort experiments in reverse chronological order (newest first)
      const sortedData = data?.sort((a: Experiment, b: Experiment) => {
        const dateA = new Date(a.updatedAt || a.createdAt)
        const dateB = new Date(b.updatedAt || b.createdAt)
        return dateB.getTime() - dateA.getTime()
      }) || []
      console.log('Sorted experiments data:', sortedData)
      
      // Only update state if data has actually changed
      setExperiments(prevExperiments => {
        console.log('Previous experiments:', prevExperiments.length, 'items')
        console.log('New experiments:', sortedData.length, 'items')
        
        // Quick comparison: check length first
        if (prevExperiments.length !== sortedData.length) {
          console.log('Length changed, updating experiments list')
          return sortedData
        }
        
        // If same length, check if all IDs match in same order
        const hasChanges = prevExperiments.some((prev, index) => {
          const current = sortedData[index]
          return !current || prev.id !== current.id || prev.updatedAt !== current.updatedAt
        })
        
        if (hasChanges) {
          console.log('Experiments data changed, updating list')
          return sortedData
        } else {
          console.log('No changes detected, keeping previous data')
          return prevExperiments
        }
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load experiments')
    } finally {
      setIsLoading(false)
    }
  }, [selectedAccount?.id])

  useEffect(() => {
    loadExperiments()
  }, [loadExperiments])

  const handleEditExperiment = useCallback((experimentId: string) => {
    console.log('Edit experiment:', experimentId)
    setIsEditMode(true)
  }, [])

  const handleDuplicateExperiment = useCallback(async (experimentId: string) => {
    console.log('handleDuplicateExperiment called with:', experimentId)
    try {
      const experiment = experiments.find(exp => exp.id === experimentId)
      console.log('Found experiment:', experiment)
      if (!experiment) {
        toast.error('Experiment not found')
        return
      }

      console.log('Creating duplicate experiment...')
      console.log('Selected account:', selectedAccount?.id)
      
      if (!selectedAccount?.id) {
        toast.error('No account selected')
        return
      }
      
      // Since experiments don't have names, we'll need to create a description
      // that indicates it's a duplicate. For now, let's just duplicate it as-is
      const { data: newExperiment } = await (client.models.Experiment.create as any)({
        featured: experiment.featured || false,
        templateId: experiment.templateId || null,
        code: experiment.code || null, // Copy the code if it exists
        rootNodeId: null, // Will be set after creating nodes
        scorecardId: experiment.scorecardId,
        scoreId: experiment.scoreId,
        accountId: selectedAccount.id,
      })

      console.log('New experiment created:', newExperiment)
      if (newExperiment) {
        // TODO: Copy the experiment nodes and versions from the original
        // For now, just refresh the experiments list
        await loadExperiments(true) // Force reload to ensure duplicate appears
        // Select the newly created duplicate experiment
        handleSelectExperiment(newExperiment.id)
        toast.success('Experiment duplicated successfully')
      }
    } catch (error) {
      console.error('Error duplicating experiment:', error)
      toast.error('Failed to duplicate experiment')
    }
  }, [experiments, loadExperiments, handleSelectExperiment, selectedAccount])

  // Handle URL synchronization for browser back/forward navigation
  useEffect(() => {
    const syncFromUrl = () => {
      const experimentMatch = window.location.pathname.match(/\/lab\/experiments\/([^\/]+)/)
      const idFromUrl = experimentMatch ? (experimentMatch[1] as string) : null
      // Only sync on back/forward, not on programmatic changes immediately after click
      setSelectedExperimentId(prev => prev === idFromUrl ? prev : idFromUrl)
    }
    
    // Listen for browser back/forward navigation
    window.addEventListener('popstate', syncFromUrl)
    return () => window.removeEventListener('popstate', syncFromUrl)
  }, [])

  // Refresh experiments when returning to the dashboard (e.g., from creation page)
  // Only refresh if data is stale (older than 30 seconds) to prevent excessive re-renders
  useEffect(() => {
    const handleFocus = () => {
      const now = Date.now()
      const isStale = now - lastLoadTimeRef.current > 30000 // 30 seconds
      
      // Only refresh if we're on the experiments dashboard page AND data is stale
      if (isStale && 
          (window.location.pathname === '/lab/experiments' || 
           window.location.pathname.startsWith('/lab/experiments/'))) {
        loadExperiments(true) // Force reload on focus if stale
      }
    }
    
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [loadExperiments])

  const handleCreateExperiment = () => {
    setShowTemplateSelector(true)
  }

  const handleCreateExperimentFromTemplate = async (template: Schema['ExperimentTemplate']['type']) => {
    if (!selectedAccount?.id) {
      toast.error('No account selected')
      return
    }

    try {
      console.log('Creating experiment from template:', { 
        templateId: template.id, 
        templateName: template.name,
        templateCode: template.template?.substring(0, 100) + '...'
      })
      
      // Create experiment with template reference and copy template code
      const createInput = {
        featured: false,
        templateId: template.id,
        code: template.template, // Copy template YAML code to experiment
        rootNodeId: null, // Will be set when nodes are created
        scorecardId: selectedScorecard || null,
        scoreId: selectedScore || null,
        accountId: selectedAccount.id,
      }
      
      console.log('Create input:', createInput)
      
      const result = await (client.models.Experiment.create as any)(createInput as any)
      const { data: newExperiment, errors } = result

      if (errors && errors.length > 0) {
        console.error('GraphQL errors creating experiment:', errors)
        toast.error('Failed to create experiment: ' + errors.map((e: any) => e.message).join(', '))
        return
      }

      if (newExperiment) {
        console.log('Experiment created successfully:', newExperiment)
        // Refresh experiments list and select the new experiment
        console.log('About to reload experiments for newly created experiment:', newExperiment.id)
        await loadExperiments(true) // Force reload to ensure new experiment appears
        console.log('Finished reloading experiments')
        handleSelectExperiment(newExperiment.id)
        // Close template selector
        setShowTemplateSelector(false)
        toast.success(`Experiment created from template "${template.name}"`)
      } else {
        console.error('No experiment data returned')
        toast.error('Failed to create experiment: No data returned')
      }
    } catch (error) {
      console.error('Error creating experiment from template:', error)
      toast.error('Failed to create experiment from template')
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

  const handleDelete = async (experimentId: string) => {
    try {
      await (client.models.Experiment.delete as any)({ id: experimentId })
      setExperiments(prev => prev.filter(exp => exp.id !== experimentId))
      if (selectedExperimentId === experimentId) {
        setSelectedExperimentId(null)
        setIsEditMode(false)
        // Update URL when deleting the currently selected experiment
        window.history.pushState(null, '', '/lab/experiments')
      }
      toast.success('Experiment deleted successfully')
    } catch (error) {
      console.error('Error deleting experiment:', error)
      toast.error('Failed to delete experiment')
    }
  }

  // Transform experiments to ExperimentTaskData - memoized to prevent unnecessary re-renders
  const transformExperiment = useCallback((experiment: Experiment): ExperimentTaskData => ({
    id: experiment.id,
    title: `${experiment.scorecard?.name || 'Experiment'} - ${experiment.score?.name || 'Score'}`,
    featured: experiment.featured || false,
    rootNodeId: experiment.rootNodeId || undefined,
    createdAt: experiment.createdAt,
    updatedAt: experiment.updatedAt,
    scorecard: experiment.scorecard ? { name: experiment.scorecard.name } : null,
    score: experiment.score ? { name: experiment.score.name } : null,
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
            <Button onClick={handleCreateExperiment} disabled={isLoading}>
              <Plus className="h-4 w-4 mr-2" />
              New Experiment
            </Button>
          </div>
        </div>
        
        {error ? (
          <div className="text-center text-destructive p-8">
            <p>Error loading experiments: {error}</p>
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


  // Render selected experiment detail or edit form
  const renderSelectedExperiment = () => {
    if (!selectedExperimentId) return null
    const experiment = experiments.find(exp => exp.id === selectedExperimentId)
    if (!experiment) return null

    // If in edit mode, render the edit form instead of the detail view
    if (isEditMode) {
      return (
        <ExperimentDetail 
          experimentId={selectedExperimentId}
          initialEditMode={true}
          onSave={() => {
            // Exit edit mode and refresh experiments list after save
            setIsEditMode(false)
            // Reload experiments to get updated data
            loadExperiments(true)
          }}
          onCancel={() => {
            // Exit edit mode without saving
            setIsEditMode(false)
          }}
        />
      )
    }

    return (
      <ExperimentTask
        variant="detail"
        experiment={transformExperiment(experiment)}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={handleCloseExperiment}
        onDelete={handleDelete}
        onEdit={handleEditExperiment}
        onDuplicate={handleDuplicateExperiment}
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
          <Button onClick={handleCreateExperiment}>
            <Plus className="h-4 w-4 mr-2" />
            Create
          </Button>
        </div>
      </div>

      {/* Experiments Content */}
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <AnimatePresence mode="popLayout">
          <motion.div 
            key="experiments-layout"
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
              className={`${selectedExperimentId && !isNarrowViewport && isFullWidth ? 'hidden' : 'flex-1'} h-full overflow-auto`}
              style={selectedExperimentId && !isNarrowViewport && !isFullWidth ? {
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
                {experiments.length === 0 ? (
                  <div className="text-center p-8">
                    <Waypoints className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <h3 className="text-lg font-medium mb-2">No experiments found</h3>
                    <p className="text-muted-foreground mb-4">
                      Get started by creating your first experiment.
                    </p>
                    <Button onClick={handleCreateExperiment}>
                      <Plus className="h-4 w-4 mr-2" />
                      New Experiment
                    </Button>
                  </div>
                ) : (
                  <div className={`
                    grid gap-3
                    ${selectedExperimentId && !isNarrowViewport && !isFullWidth ? 'grid-cols-1' : 'grid-cols-1 @[640px]:grid-cols-2'}
                  `}>
                    {experiments.map((experiment) => {
                      const clickHandler = getExperimentClickHandler(experiment.id)
                      
                      return (
                        <div 
                          key={experiment.id}
                          role="button"
                          tabIndex={0}
                          onClick={clickHandler}
                          onKeyDown={(ev) => {
                            if (ev.key === 'Enter' || ev.key === ' ') {
                              ev.preventDefault()
                              clickHandler()
                            }
                          }}
                          aria-pressed={experiment.id === selectedExperimentId}
                          data-selected={experiment.id === selectedExperimentId ? 'true' : 'false'}
                        >
                          <ExperimentTask
                            variant="grid"
                            experiment={transformExperiment(experiment)}
                            onClick={clickHandler}
                            isSelected={experiment.id === selectedExperimentId}
                            onDelete={handleDelete}
                            onEdit={handleEditExperiment}
                            onDuplicate={handleDuplicateExperiment}
                          />
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </motion.div>

            {/* Divider for split view */}
            {selectedExperimentId && !isNarrowViewport && !isFullWidth && (
              <div
                className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
                onMouseDown={handleDragStart}
              >
                <div className="absolute inset-0 rounded-full transition-colors duration-150 
                  group-hover:bg-accent" />
              </div>
            )}

            {/* Right panel - experiment detail view */}
            <AnimatePresence>
              {selectedExperimentId && !isNarrowViewport && !isFullWidth && (
                <motion.div 
                  key={`experiment-detail-${selectedExperimentId}`}
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
                  {renderSelectedExperiment()}
                </motion.div>
              )}
            </AnimatePresence>

          </motion.div>
        </AnimatePresence>
        
        {/* Full-screen view for mobile or full-width mode */}
        {selectedExperimentId && (isNarrowViewport || isFullWidth) && (
          <div className="fixed inset-0 z-50 overflow-y-auto">
            {renderSelectedExperiment()}
          </div>
        )}
      </div>

      {/* Template Selector Modal */}
      {selectedAccount && (
        <TemplateSelector
          accountId={selectedAccount.id}
          open={showTemplateSelector}
          onOpenChange={setShowTemplateSelector}
          onTemplateSelect={handleCreateExperimentFromTemplate}
        />
      )}
    </div>
  )
}

// Memoize the component to prevent unnecessary re-renders from parent
export default React.memo(ExperimentsDashboard)
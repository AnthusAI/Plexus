"use client"
import React, { useState, useEffect, useCallback } from "react"
import { useRouter, usePathname, useParams } from "next/navigation"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Button } from "@/components/ui/button"
import { Plus, FileCode2 } from "lucide-react"
import { toast } from "sonner"
import TemplateTask, { TemplateTaskData } from "@/components/TemplateTask"
import { motion, AnimatePresence } from "framer-motion"
import { useMediaQuery } from "@/hooks/use-media-query"
import { useAccount } from '@/app/contexts/AccountContext'

type ExperimentTemplate = Schema['ExperimentTemplate']['type']
type CreateExperimentTemplateInput = Schema['ExperimentTemplate']['createType']

const client = generateClient<Schema>()

interface TemplatesDashboardProps {
  initialSelectedTemplateId?: string | null
}

// Default template content
const DEFAULT_TEMPLATE_CONTENT = `class: "BeamSearch"

value: |
  -- Extract accuracy score from experiment node's structured data
  local score = experiment_node.value.accuracy or 0
  -- Apply cost penalty to balance performance vs efficiency  
  local penalty = (experiment_node.value.cost or 0) * 0.1
  -- Return single scalar value (higher is better)
  return score - penalty

exploration: |
  You are a hypothesis engine in an automated experiment running process for 
  optimizing scorecard score configurations in a reinforcement learning feedback loop system.
  
  Your role is to analyze feedback alignment data and generate testable hypotheses 
  for improving AI score accuracy based on human reviewer corrections.
  
  You have access to feedback analysis tools that show where human reviewers 
  corrected AI scores, plus detailed item information for understanding the 
  underlying content that caused misalignment.
  
  Your goal is to identify patterns in misclassification and propose specific 
  configuration changes that could reduce these errors.`

export default function TemplatesDashboard({ initialSelectedTemplateId }: TemplatesDashboardProps = {}) {
  const router = useRouter()
  const pathname = usePathname()
  const params = useParams()
  const { selectedAccount } = useAccount()
  
  // Extract template ID from URL params if present, or use the prop
  const templateIdFromParams = (params && 'id' in params) ? params.id as string : null
  const finalInitialTemplateId = initialSelectedTemplateId || templateIdFromParams
  
  const [templates, setTemplates] = useState<ExperimentTemplate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(finalInitialTemplateId)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")

  const handleSelectTemplate = useCallback((id: string | null) => {
    setSelectedTemplateId(id)
    const newPathname = id ? `/lab/templates/${id}` : '/lab/templates'
    window.history.pushState(null, '', newPathname)
    
    if (isNarrowViewport && id) {
      setIsFullWidth(true)
    }
  }, [isNarrowViewport])

  const handleCloseTemplate = useCallback(() => {
    setSelectedTemplateId(null)
    setIsFullWidth(false)
    setEditingTemplateId(null)
    window.history.pushState(null, '', '/lab/templates')
  }, [])

  const getTemplateClickHandler = useCallback((templateId: string) => {
    return (e?: React.MouseEvent | React.SyntheticEvent | any) => {
      if (e && typeof e.preventDefault === 'function') {
        e.preventDefault()
      }
      setIsFullWidth(false)
      try { (document.activeElement as HTMLElement | null)?.blur?.() } catch {}
      handleSelectTemplate(templateId)
    }
  }, [handleSelectTemplate])

  const loadTemplates = useCallback(async () => {
    if (!selectedAccount?.id) {
      setTemplates([])
      setIsLoading(false)
      return
    }

    try {
      setIsLoading(true)
      const { data } = await (client.models.ExperimentTemplate.listExperimentTemplateByAccountIdAndUpdatedAt as any)({
        accountId: selectedAccount.id,

      })
      setTemplates(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load templates')
    } finally {
      setIsLoading(false)
    }
  }, [selectedAccount?.id])

  useEffect(() => {
    loadTemplates()
  }, [loadTemplates])

  const handleEditTemplate = useCallback((templateId: string) => {
    if (templateId === '') {
      // Exit edit mode
      setEditingTemplateId(null)
    } else {
      setEditingTemplateId(templateId)
    }
  }, [])

  const handleDuplicateTemplate = useCallback(async (templateId: string) => {
    try {
      const template = templates.find(t => t.id === templateId)
      if (!template) {
        toast.error('Template not found')
        return
      }

      if (!selectedAccount?.id) {
        toast.error('No account selected')
        return
      }
      
      const input = {
        name: `${template.name} (Copy)`,
        description: template.description,
        template: template.template,
        version: template.version,
        category: template.category,
        isDefault: false,
        accountId: selectedAccount.id
      }

      const { data: newTemplate } = await (client.models.ExperimentTemplate.create as any)(input as any)

      if (newTemplate) {
        loadTemplates()
        handleSelectTemplate(newTemplate.id)
        toast.success('Template duplicated successfully')
      }
    } catch (error) {
      console.error('Error duplicating template:', error)
      toast.error('Failed to duplicate template')
    }
  }, [templates, loadTemplates, handleSelectTemplate, selectedAccount])

  const handleCreateTemplate = async () => {
    if (!selectedAccount?.id) {
      toast.error('No account selected')
      return
    }

    try {
      const input = {
        name: 'New Template',
        description: 'A new experiment template',
        template: DEFAULT_TEMPLATE_CONTENT,
        version: '1.0',
        category: 'hypothesis_generation',
        isDefault: false,
        accountId: selectedAccount.id
      }

      const { data: newTemplate } = await (client.models.ExperimentTemplate.create as any)(input as any)

      if (newTemplate) {
        await loadTemplates()
        handleSelectTemplate(newTemplate.id)
        setEditingTemplateId(newTemplate.id) // Start editing immediately
        toast.success('New template created')
      }
    } catch (error) {
      console.error('Error creating template:', error)
      toast.error('Failed to create template')
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

  const handleDeleteTemplate = async (templateId: string) => {
    try {
      await (client.models.ExperimentTemplate.delete as any)({ id: templateId })
      setTemplates(prev => prev.filter(t => t.id !== templateId))
      if (selectedTemplateId === templateId) {
        setSelectedTemplateId(null)
        setEditingTemplateId(null)
        window.history.pushState(null, '', '/lab/templates')
      }
      toast.success('Template deleted successfully')
    } catch (error) {
      console.error('Error deleting template:', error)
      toast.error('Failed to delete template')
    }
  }

  const handleSaveTemplate = async (templateId: string, updates: Partial<TemplateTaskData>) => {
    try {
      const updateData: any = {
        id: templateId,
        ...updates
      }

      await (client.models.ExperimentTemplate.update as any)(updateData)
      
      // Update local state
      setTemplates(prev => prev.map(t => 
        t.id === templateId ? { ...t, ...updates } : t
      ))
      
      setEditingTemplateId(null)
      toast.success('Template saved successfully')
    } catch (error) {
      console.error('Error saving template:', error)
      throw error // Re-throw so TemplateTask can handle it
    }
  }

  // Transform template to TemplateTaskData
  const transformTemplate = (template: ExperimentTemplate): TemplateTaskData => ({
    id: template.id,
    title: template.name,
    name: template.name,
    description: template.description || undefined,
    template: template.template,
    version: template.version,
    category: template.category || undefined,
    isDefault: template.isDefault || false,
    createdAt: template.createdAt,
    updatedAt: template.updatedAt,
  })
  
  const selectedTemplate = selectedTemplateId 
    ? templates.find(t => t.id === selectedTemplateId)
    : null

  // Handle URL synchronization for browser back/forward navigation
  useEffect(() => {
    const syncFromUrl = () => {
      const templateMatch = window.location.pathname.match(/\/lab\/templates\/([^\/]+)/)
      const idFromUrl = templateMatch ? (templateMatch[1] as string) : null
      setSelectedTemplateId(prev => prev === idFromUrl ? prev : idFromUrl)
    }
    
    window.addEventListener('popstate', syncFromUrl)
    return () => window.removeEventListener('popstate', syncFromUrl)
  }, [])

  // Refresh templates when returning to the dashboard
  useEffect(() => {
    const handleFocus = () => {
      if (window.location.pathname === '/lab/templates' || 
          window.location.pathname.startsWith('/lab/templates/')) {
        loadTemplates()
      }
    }
    
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [loadTemplates])

  // Render selected template detail view
  const renderSelectedTemplate = () => {
    if (!selectedTemplateId) return null
    const template = templates.find(t => t.id === selectedTemplateId)
    if (!template) return null

    return (
      <TemplateTask
        variant="detail"
        template={transformTemplate(template)}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={handleCloseTemplate}
        onDelete={handleDeleteTemplate}
        onEdit={handleEditTemplate}
        onDuplicate={handleDuplicateTemplate}
        onSave={handleSaveTemplate}
        isEditing={editingTemplateId === selectedTemplateId}
      />
    )
  }

  // Loading and error states
  if (isLoading || error) {
    return (
      <div className="@container flex flex-col h-full p-3 overflow-hidden">
        <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
          <div className="@[600px]:flex-grow w-full">
            <div className="flex items-center gap-2">
              <FileCode2 className="h-5 w-5 text-muted-foreground" />
              <h1 className="text-lg font-semibold">Experiment Templates</h1>
            </div>
          </div>
          <div className="flex-shrink-0">
            <Button onClick={handleCreateTemplate} disabled={isLoading}>
              <Plus className="h-4 w-4 mr-2" />
              New Template
            </Button>
          </div>
        </div>
        
        {error ? (
          <div className="text-center text-destructive p-8">
            <p>Error loading templates: {error}</p>
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

  return (
    <div className="@container flex flex-col h-full p-3 overflow-hidden">
      {/* Fixed header */}
      <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
        <div className="@[600px]:flex-grow w-full">
          <div className="flex items-center gap-2">
            <FileCode2 className="h-5 w-5 text-muted-foreground" />
            <h1 className="text-lg font-semibold">Experiment Templates</h1>
          </div>
        </div>
        <div className="flex-shrink-0">
          <Button onClick={handleCreateTemplate}>
            <Plus className="h-4 w-4 mr-2" />
            New Template
          </Button>
        </div>
      </div>

      {/* Templates Content */}
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <AnimatePresence mode="popLayout">
          <motion.div 
            key="templates-layout"
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
              className={`${selectedTemplateId && !isNarrowViewport && isFullWidth ? 'hidden' : 'flex-1'} h-full overflow-auto`}
              style={selectedTemplateId && !isNarrowViewport && !isFullWidth ? {
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
                {templates.length === 0 ? (
                  <div className="text-center p-8">
                    <FileCode2 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <h3 className="text-lg font-medium mb-2">No templates found</h3>
                    <p className="text-muted-foreground mb-4">
                      Get started by creating your first experiment template.
                    </p>
                    <Button onClick={handleCreateTemplate}>
                      <Plus className="h-4 w-4 mr-2" />
                      New Template
                    </Button>
                  </div>
                ) : (
                  <div className={`
                    grid gap-3
                    ${selectedTemplateId && !isNarrowViewport && !isFullWidth ? 'grid-cols-1' : 'grid-cols-1 @[640px]:grid-cols-2'}
                  `}>
                    {templates.map((template) => {
                      const clickHandler = getTemplateClickHandler(template.id)
                      
                      return (
                        <div 
                          key={template.id}
                          role="button"
                          tabIndex={0}
                          onClick={clickHandler}
                          onKeyDown={(ev) => {
                            if (ev.key === 'Enter' || ev.key === ' ') {
                              ev.preventDefault()
                              clickHandler()
                            }
                          }}
                          aria-pressed={template.id === selectedTemplateId}
                          data-selected={template.id === selectedTemplateId ? 'true' : 'false'}
                        >
                          <TemplateTask
                            variant="grid"
                            template={transformTemplate(template)}
                            onClick={clickHandler}
                            isSelected={template.id === selectedTemplateId}
                            onDelete={handleDeleteTemplate}
                            onEdit={handleEditTemplate}
                            onDuplicate={handleDuplicateTemplate}
                          />
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </motion.div>

            {/* Divider for split view */}
            {selectedTemplateId && !isNarrowViewport && !isFullWidth && (
              <div
                className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
                onMouseDown={handleDragStart}
              >
                <div className="absolute inset-0 rounded-full transition-colors duration-150 
                  group-hover:bg-accent" />
              </div>
            )}

            {/* Right panel - template detail view */}
            <AnimatePresence>
              {selectedTemplateId && !isNarrowViewport && !isFullWidth && (
                <motion.div 
                  key={`template-detail-${selectedTemplateId}`}
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
                  {renderSelectedTemplate()}
                </motion.div>
              )}
            </AnimatePresence>

          </motion.div>
        </AnimatePresence>
        
        {/* Full-screen view for mobile or full-width mode */}
        {selectedTemplateId && (isNarrowViewport || isFullWidth) && (
          <div className="fixed inset-0 z-50 overflow-y-auto">
            {renderSelectedTemplate()}
          </div>
        )}
      </div>
    </div>
  )
}
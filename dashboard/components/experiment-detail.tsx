"use client"
import React, { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Card, CardContent } from "@/components/ui/card"
import { ArrowLeft, Save, Trash2, Waypoints, FileText, ChevronRight, ChevronDown } from "lucide-react"
import { toast } from "sonner"
import Editor from "@monaco-editor/react"
import { useYamlLinter, useLintMessageHandler } from "@/hooks/use-yaml-linter"
import YamlLinterPanel from "@/components/ui/yaml-linter-panel"
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions, configureYamlLanguage } from "@/lib/monaco-theme"
import ExperimentTask from "./ExperimentTask"
import ExperimentNodesList from "./experiment-nodes-list"
import { useAccount } from '@/app/contexts/AccountContext'
import ScorecardContext from '@/components/ScorecardContext'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

// Types based on our GraphQL schema
type Experiment = Schema['Experiment']['type']

const client = generateClient<Schema>()

// Minimal fallback for YAML editor - actual templates come from backend service
const MINIMAL_YAML_FALLBACK = `class: "BeamSearch"
# Default experiment template will be loaded from backend...`




interface Props {
  experimentId?: string
  onSave?: () => void
  onCancel?: () => void
  initialEditMode?: boolean
}

export default function ExperimentDetail({ experimentId, onSave, onCancel, initialEditMode = false }: Props) {
  const router = useRouter()
  const { selectedAccount } = useAccount()
  const [experiment, setExperiment] = useState<Experiment | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(initialEditMode || !experimentId) // true for new experiments or when initialEditMode is true
  const [formData, setFormData] = useState({
    featured: false,
    code: MINIMAL_YAML_FALLBACK,
    scorecardId: null as string | null,
    scoreId: null as string | null
  })
  const [loadedYaml, setLoadedYaml] = useState<string>('')
  const [originalFormData, setOriginalFormData] = useState({
    featured: false,
    code: MINIMAL_YAML_FALLBACK,
    scorecardId: null as string | null,
    scoreId: null as string | null
  })
  const [hasChanges, setHasChanges] = useState(false)

  const isNew = !experimentId

  // YAML linting integration
  const { lintResult, isLinting, setupMonacoIntegration, jumpToLine } = useYamlLinter({
    context: 'experiment',
    debounceMs: 500,
    showMonacoMarkers: true
  })
  const handleLintMessageClick = useLintMessageHandler(jumpToLine)

  // Load experiment data
  useEffect(() => {
    const loadExperiment = async () => {
      if (!experimentId) {
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        const { data } = await (client.models.Experiment.get as any)({ 
          id: experimentId 
        }, {
          selectionSet: ['id', 'featured', 'templateId', 'code', 'rootNodeId', 'createdAt', 'updatedAt', 'scorecardId', 'scoreId', 'template.template', 'scorecard.name', 'score.name']
        })
        if (data) {
          setExperiment(data)
          
          // Load YAML from experiment's code field, fallback to template, then to default
          const yamlContent = data.code || data.template?.template || MINIMAL_YAML_FALLBACK
          
          setLoadedYaml(yamlContent)
          const initialData = {
            featured: data.featured || false,
            code: yamlContent,
            scorecardId: data.scorecardId || null,
            scoreId: data.scoreId || null
          }
          setFormData(initialData)
          setOriginalFormData(initialData)
          setHasChanges(false)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load experiment')
      } finally {
        setIsLoading(false)
      }
    }

    loadExperiment()
  }, [experimentId])

  const handleSave = async () => {
    try {
      // Validate YAML has no errors before saving
      if (lintResult && !lintResult.is_valid && lintResult.error_count > 0) {
        toast.error('Please fix YAML errors before saving')
        return
      }

      // Validate required fields
      if (!formData.scorecardId) {
        toast.error('Please select a scorecard')
        return
      }

      if (!formData.scoreId) {
        toast.error('Please select a score')
        return
      }

      if (isNew) {
        // Validate account is selected
        if (!selectedAccount?.id) {
          toast.error('No account selected')
          return
        }

        const createData = {
          featured: formData.featured || false,
          code: formData.code,
          scorecardId: formData.scorecardId,
          scoreId: formData.scoreId,
          accountId: selectedAccount.id,
          templateId: null, // Not creating from template in this flow
          rootNodeId: null, // Will be set when nodes are created
        }

        console.log('Creating experiment with data:', createData)
        console.log('Data types:', {
          featured: typeof createData.featured,
          scorecardId: typeof createData.scorecardId,
          scoreId: typeof createData.scoreId,
          accountId: typeof createData.accountId,
        })

        // Create new experiment (matching the format used in duplicate function)
        const result = await (client.models.Experiment.create as any)(createData)

        if (result.errors) {
          console.error('Experiment creation errors:', result.errors)
          toast.error('Failed to create experiment: ' + result.errors.map((e: any) => e.message).join(', '))
          return
        }

        if (!result.data) {
          console.error('No experiment data returned')
          toast.error('Failed to create experiment: No data returned')
          return
        }

        const experimentData = result.data

        console.log('Experiment created successfully:', experimentData)
        
        toast.success('Experiment created successfully')
        // Always go back to experiments list and select the new experiment
        router.push(`/lab/experiments/${experimentData.id}`)
      } else if (experiment) {
        // Update existing experiment
        const { data } = await (client.models.Experiment.update as any)({
          id: experiment.id,
          featured: formData.featured,
          code: formData.code,
          scorecardId: formData.scorecardId,
          scoreId: formData.scoreId,
        })
        
        if (data) {
          setExperiment(data)
          setOriginalFormData({ ...formData })
        }
        toast.success('Experiment updated successfully')
        setIsEditing(false)
        // Call onSave callback if provided
        if (onSave) {
          onSave()
        }
      }
      setHasChanges(false)
    } catch (error) {
      toast.error(`Failed to ${isNew ? 'create' : 'update'} experiment`)
      console.error('Error saving experiment:', error)
    }
  }

  const handleCancel = () => {
    setFormData({ ...originalFormData })
    setHasChanges(false)
    // Call onCancel callback if provided
    if (onCancel) {
      onCancel()
    }
  }

  const handleDelete = async () => {
    if (!experiment || isNew) return
    
    try {
      await (client.models.Experiment.delete as any)({ id: experiment.id })
      toast.success('Experiment deleted successfully')
      router.push('/lab/experiments')
    } catch (error) {
      toast.error('Failed to delete experiment')
      console.error('Error deleting experiment:', error)
    }
  }

  const handleBack = () => {
    router.push('/lab/experiments')
  }

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <Button variant="ghost" size="sm" onClick={handleBack}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Waypoints className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold">Loading...</h1>
        </div>
        <Card>
          <CardContent className="p-6">
            <div className="animate-pulse space-y-4">
              <div className="h-4 bg-gray-200 rounded w-1/4"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
              <div className="h-4 bg-gray-200 rounded w-1/3"></div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error && !isNew) {
    return (
      <div className="p-6">
        <div className="flex items-center gap-3 mb-6">
          <Button variant="ghost" size="sm" onClick={handleBack}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Waypoints className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold">Error</h1>
        </div>
        <Card>
          <CardContent className="p-6">
            <div className="text-center text-destructive">
              <p>Error loading experiment: {error}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Show header only when not embedded in dashboard (i.e., when onCancel is not provided)
  const showHeader = !onCancel
  
  return (
    <div className="bg-background p-3">
      <div className="bg-card p-3 rounded-lg">
      {showHeader && (
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={handleBack}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <Waypoints className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">
              {isNew ? 'New Experiment' : 'Experiment'}
            </h1>
          </div>
          
          <div className="flex gap-2">
            {!isNew && !isEditing && (
              <Button variant="outline" onClick={() => setIsEditing(true)}>
                Edit
              </Button>
            )}
            {(isNew || isEditing) && (
              <Button onClick={handleSave}>
                <Save className="h-4 w-4 mr-2" />
                {isNew ? 'Create' : 'Save'}
              </Button>
            )}
            {experiment && !isNew && (
              <Button variant="destructive" onClick={handleDelete}>
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </Button>
            )}
          </div>
        </div>
      )}

      <div className="space-y-6">
        <div>
          <div className="mb-6">
            <h3 className="text-lg font-semibold">Edit Experiment</h3>
          </div>
          <div className="space-y-6">
            {/* Scorecard and Score Selection */}
            {(isEditing || isNew) && (
              <div className="space-y-2">
                <ScorecardContext 
                  selectedScorecard={formData.scorecardId}
                  setSelectedScorecard={(scorecardId) => {
                    const newFormData = { ...formData, scorecardId, scoreId: null } // Reset score when scorecard changes
                    setFormData(newFormData)
                    const changed = JSON.stringify(newFormData) !== JSON.stringify(originalFormData)
                    setHasChanges(changed)
                  }}
                  selectedScore={formData.scoreId}
                  setSelectedScore={(scoreId) => {
                    const newFormData = { ...formData, scoreId }
                    setFormData(newFormData)
                    const changed = JSON.stringify(newFormData) !== JSON.stringify(originalFormData)
                    setHasChanges(changed)
                  }}
                />
              </div>
            )}

            {/* YAML Configuration - Show in both edit and read-only modes */}
            <div className="space-y-2">
              <Label>YAML Configuration</Label>
              
              {(isEditing || isNew) ? (
                  // Edit mode - full Monaco editor
                  <div>
                    <div className="overflow-hidden">
                      <Editor
                        height="400px"
                        defaultLanguage="yaml"
                        value={formData.code}
                        onChange={(value) => {
                          const newFormData = { ...formData, code: value || '' }
                          setFormData(newFormData)
                          // Check if there are changes
                          const changed = JSON.stringify(newFormData) !== JSON.stringify(originalFormData)
                          setHasChanges(changed)
                        }}
                        onMount={(editor, monaco) => {
                          // Configure Monaco editor for YAML
                          defineCustomMonacoThemes(monaco)
                          applyMonacoTheme(monaco)
                          setupMonacoThemeWatcher(monaco)
                          configureYamlLanguage(monaco)
                          
                          // Set up linting integration
                          setupMonacoIntegration(editor, monaco)
                        }}
                        options={{
                          ...getCommonMonacoOptions(),
                          minimap: { enabled: false },
                          scrollBeyondLastLine: false,
                          wordWrap: 'on',
                          tabSize: 2,
                          insertSpaces: true,
                        }}
                      />
                    </div>

                    {/* YAML Linting Panel */}
                    <YamlLinterPanel
                      result={lintResult || undefined}
                      onMessageClick={handleLintMessageClick}
                      className="mt-2"
                    />
                  </div>
                ) : (
                  // Read-only mode - read-only Monaco editor
                  <div className="overflow-hidden">
                    <Editor
                      height="400px"
                      defaultLanguage="yaml"
                      value={loadedYaml || MINIMAL_YAML_FALLBACK}
                      onMount={(_, monaco) => {
                        // Configure Monaco editor for YAML
                        defineCustomMonacoThemes(monaco)
                        applyMonacoTheme(monaco)
                        setupMonacoThemeWatcher(monaco)
                        configureYamlLanguage(monaco)
                      }}
                      options={{
                        ...getCommonMonacoOptions(),
                        readOnly: true,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        wordWrap: 'on',
                        tabSize: 2,
                        insertSpaces: true,
                      }}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Featured Toggle and Save/Cancel - only in edit mode */}
            {(isEditing || isNew) && (
              <div className="space-y-4">
                {/* Featured Toggle */}
                <div className="flex items-center space-x-2">
                  <Switch
                    id="featured"
                    checked={formData.featured}
                    onCheckedChange={(checked) => {
                      const newFormData = { ...formData, featured: checked }
                      setFormData(newFormData)
                      // Check if there are changes
                      const changed = JSON.stringify(newFormData) !== JSON.stringify(originalFormData)
                      setHasChanges(changed)
                    }}
                  />
                  <Label htmlFor="featured">Featured</Label>
                </div>
                
                {/* Save/Cancel Buttons - only show when there are changes */}
                {hasChanges && (
                  <div className="flex gap-2 justify-end">
                    <Button variant="outline" onClick={handleCancel}>
                      Cancel
                    </Button>
                    <Button onClick={handleSave}>
                      <Save className="h-4 w-4 mr-2" />
                      {isNew ? 'Create' : 'Save'}
                    </Button>
                  </div>
                )}
              </div>
            )}


            {/* Read-only fields for existing experiments */}
            {experiment && !isNew && !isEditing && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t">
                {experiment.scorecardId && (
                  <div className="space-y-2">
                    <Label>Scorecard</Label>
                    <div className="px-3 py-2 bg-muted rounded-md text-sm">
                      {experiment.scorecard?.name || experiment.scorecardId}
                    </div>
                  </div>
                )}
                {experiment.scoreId && (
                  <div className="space-y-2">
                    <Label>Score</Label>
                    <div className="px-3 py-2 bg-muted rounded-md text-sm">
                      {experiment.score?.name || experiment.scoreId}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {experiment && (
          <ExperimentTask experiment={experiment as any} variant="detail" />
        )}

        {experiment && !isNew && (
          <ExperimentNodesList experimentId={experiment.id} />
        )}

        {!experiment && !isNew && (
          <Card>
            <CardContent className="p-6">
              <div className="text-center text-muted-foreground">
                Experiment not found
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
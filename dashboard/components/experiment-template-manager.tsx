"use client"

import React, { useState, useEffect } from 'react'
import { generateClient } from 'aws-amplify/data'
import type { Schema } from '@/amplify/data/resource'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Trash2, Edit, Plus, Copy, Download, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { Editor } from '@monaco-editor/react'
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher } from '@/lib/monaco-theme'

const client = generateClient<Schema>()

// Types
// NOTE: ProcedureTemplate table was removed. Templates are now Procedures with isTemplate=true
type ProcedureTemplate = Schema['Procedure']['type']
type CreateProcedureTemplateInput = Schema['Procedure']['createType']

interface ProcedureTemplateManagerProps {
  accountId: string
  onTemplateSelect?: (template: ProcedureTemplate) => void
}

// Default template content with state machine
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
  configuration changes that could reduce these errors.

# Advanced conversation flow with tool-usage-based state machine
conversation_flow:
  # Initial state - all chat sessions start here
  initial_state: "investigation"
  
  # State machine definitions
  states:
    investigation:
      description: "Deep exploration of feedback data and individual item analysis"
      prompt_template: |
        🔍 **INVESTIGATION PHASE** 🔍
        
        **Context:** You are analyzing feedback alignment for {scorecard_name} → {score_name}
        
        **Your Mission:** Understand WHY the score is misaligned by examining specific cases where human reviewers corrected the AI.
        
        **Current Progress:**
        {progress_summary}
        
        **Next Steps:** {next_action_guidance}
        
        **Available Tools:**
        - \`plexus_feedback_analysis(scorecard_name="{scorecard_name}", score_name="{score_name}")\` - Get confusion matrix and patterns
        - \`plexus_feedback_find(scorecard_name="{scorecard_name}", score_name="{score_name}", initial_value="No", final_value="Yes")\` - Find specific correction cases  
        - \`plexus_item_info(item_id="...")\` - Examine individual item details
        
        Focus on discovering actionable patterns that could inform configuration changes.
        
    pattern_analysis:
      description: "Synthesizing findings into clear patterns and root causes"
      prompt_template: |
        🧩 **PATTERN ANALYSIS PHASE** 🧩
        
        **Context:** Based on your investigation of {scorecard_name} → {score_name}
        
        **Your Mission:** Synthesize your findings into clear, actionable patterns.
        
        **Investigation Summary:**
        {investigation_summary}
        
        **Required Analysis:**
        - What are the main categories of misalignment?
        - What common characteristics lead to false positives/negatives?
        - What specific configuration changes could address these issues?
        - Which individual item IDs exemplify each error pattern?
        
        Document concrete patterns that will inform your hypotheses.
        
    hypothesis_creation:
      description: "Creating specific testable experiment nodes"
      prompt_template: |
        🚀 **HYPOTHESIS CREATION PHASE** 🚀
        
        **Context:** Creating testable solutions for {scorecard_name} → {score_name}
        
        **Your Mission:** Create 2-3 distinct experiment nodes testing different approaches.
        
        **Pattern Analysis Summary:**
        {patterns_summary}
        
        **REQUIRED ACTION:** Use \`create_experiment_node\` for each hypothesis:
        
        \`\`\`
        create_experiment_node(
            experiment_id="{experiment_id}",
            hypothesis_description="GOAL: [specific improvement] | METHOD: [exact changes] | EXAMPLES: [item IDs that exemplify the problem]",
            node_name="[descriptive name]"
        )
        \`\`\`
        
        **Note:** yaml_configuration is optional - focus on clear hypothesis descriptions with specific item examples.
        
        Create hypotheses targeting different root causes you discovered.
        
    complete:
      description: "Hypothesis generation completed successfully"
      prompt_template: |
        ✅ **HYPOTHESIS GENERATION COMPLETE** ✅
        
        Successfully created experiment nodes for testing. The next phase will involve:
        1. Running experiments with each hypothesis configuration
        2. Evaluating performance improvements
        3. Selecting the best-performing approaches
        
        Great work on the thorough analysis!

  # State transition rules (checked in order, first match wins)
  transition_rules:
    # From investigation to pattern_analysis
    - from_state: "investigation"
      to_state: "pattern_analysis"
      conditions:
        - type: "tool_usage_count"
          tool: "plexus_feedback_analysis"
          min_count: 1
        - type: "tool_usage_count" 
          tool: "plexus_feedback_find"
          min_count: 2
        - type: "tool_usage_count"
          tool: "plexus_item_info" 
          min_count: 3
        - type: "round_in_state"
          min_rounds: 2
      description: "Sufficient investigation completed - examine summary, multiple feedback cases, and individual items"
      
    # From investigation to pattern_analysis (fallback after many rounds)
    - from_state: "investigation"
      to_state: "pattern_analysis"
      conditions:
        - type: "tool_usage_count"
          tool: "plexus_feedback_analysis"
          min_count: 1
        - type: "round_in_state"
          min_rounds: 6
      description: "Extended investigation - move to analysis with available data"
      
    # From pattern_analysis to hypothesis_creation  
    - from_state: "pattern_analysis"
      to_state: "hypothesis_creation"
      conditions:
        - type: "round_in_state"
          min_rounds: 1
      description: "Analysis complete - time to create testable hypotheses"
      
    # From hypothesis_creation to complete
    - from_state: "hypothesis_creation"
      to_state: "complete"
      conditions:
        - type: "tool_usage_count"
          tool: "create_experiment_node"
          min_count: 2
      description: "Successfully created multiple experiment nodes"
      
    # Emergency transitions to prevent infinite loops
    - from_state: "investigation"
      to_state: "hypothesis_creation"
      conditions:
        - type: "round_in_state"
          min_rounds: 8
      description: "Emergency: Force hypothesis creation after extensive investigation"
      
    - from_state: "pattern_analysis" 
      to_state: "hypothesis_creation"
      conditions:
        - type: "round_in_state"
          min_rounds: 3
      description: "Emergency: Force hypothesis creation after extended analysis"

  # Escalation settings
  escalation:
    # When to start gentle pressure within each state
    gentle_pressure_after: 3
    # When to apply firm pressure within each state  
    firm_pressure_after: 5
    # Maximum total rounds before emergency termination
    max_total_rounds: 120
    
  # Guidance for specific situations
  guidance:
    missing_tools:
      plexus_feedback_analysis: "Start with the feedback analysis to understand overall error patterns and confusion matrix"
      plexus_feedback_find: "Search for specific feedback corrections to understand individual misalignment cases"
      plexus_item_info: "Examine item details to understand what content characteristics lead to errors"
      create_experiment_node: "Create testable hypotheses based on the patterns you've discovered"
      
    insufficient_investigation:
      message: |
        📊 **MORE INVESTIGATION NEEDED** 📊
        
        You need deeper analysis before moving forward:
        - Use \`plexus_feedback_find\` to examine specific correction cases
        - Use \`plexus_item_info\` to understand why particular items were misclassified
        - Look for patterns in content, wording, or context that lead to errors
        
        Quality over speed - thorough investigation leads to better hypotheses.`

export default function ProcedureTemplateManager({ accountId, onTemplateSelect }: ProcedureTemplateManagerProps) {
  const [templates, setTemplates] = useState<ProcedureTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<ProcedureTemplate | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [activeTab, setActiveTab] = useState('browse')
  const [creatingProcedureFromTemplate, setCreatingProcedureFromTemplate] = useState<string | null>(null)
  
  // Form state for creating/editing templates
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    template: DEFAULT_TEMPLATE_CONTENT,
    version: '1.0',
    category: 'hypothesis_generation',
    isDefault: false
  })

  // Load templates on mount
  useEffect(() => {
    loadTemplates()
  }, [accountId])

  const loadTemplates = async () => {
    setIsLoading(true)
    try {
      const result = await (client.models.Procedure.listProcedureByAccountIdAndUpdatedAt as any)({
        accountId: accountId,
      })

      if (result.data) {
        // Filter for templates only (isTemplate=true) and map code -> template
        const templateData = result.data
          .filter((p: any) => p.isTemplate === true)
          .map((p: any) => ({ ...p, template: p.code }))
        setTemplates(templateData)
      }
    } catch (error) {
      console.error('Error loading templates:', error)
      toast.error("Failed to load experiment templates")
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreateTemplate = async () => {
    if (!formData.name || !formData.template || !formData.version) {
      toast.error("Name, template content, and version are required")
      return
    }

    setIsLoading(true)
    try {
      const input = {
        name: formData.name,
        description: formData.description || undefined,
        code: formData.template, // Map template -> code
        version: formData.version,
        category: formData.category || undefined,
        isDefault: formData.isDefault || undefined,
        isTemplate: true, // Mark as template
        accountId: accountId
      }

      const result = await (client.models.Procedure.create as any)(input as any)
      
      if (result.data) {
        setTemplates(prev => [result.data!, ...prev])
        setActiveTab('browse')
        resetForm()
        toast.success(`Template "${formData.name}" created successfully`)
      }
    } catch (error) {
      console.error('Error creating template:', error)
      toast.error("Failed to create template")
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteTemplate = async (template: ProcedureTemplate) => {
    if (!confirm(`Are you sure you want to delete template "${template.name}"?`)) {
      return
    }

    setIsLoading(true)
    try {
      await (client.models.Procedure.delete as any)({ id: template.id })
      setTemplates(prev => prev.filter(t => t.id !== template.id))
      if (selectedTemplate?.id === template.id) {
        setSelectedTemplate(null)
      }
      toast.success(`Template "${template.name}" deleted successfully`)
    } catch (error) {
      console.error('Error deleting template:', error)
      toast.error("Failed to delete template")
    } finally {
      setIsLoading(false)
    }
  }

  const handleCopyTemplate = (template: ProcedureTemplate) => {
    // Note: We map code -> template when loading, but TypeScript doesn't know about it
    const templateCode = (template as any).template || template.code || ''
    setFormData({
      name: `${template.name} (Copy)`,
      description: template.description || '',
      template: templateCode,
      version: template.version || '1.0',
      category: template.category || 'hypothesis_generation',
      isDefault: false
    })
    setActiveTab('create')
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      template: DEFAULT_TEMPLATE_CONTENT,
      version: '1.0',
      category: 'hypothesis_generation',
      isDefault: false
    })
    setIsEditing(false)
  }

  const handleCreateProcedureFromTemplate = async (template: ProcedureTemplate) => {
    setCreatingProcedureFromTemplate(template.id)
    try {
      await onTemplateSelect?.(template)
    } finally {
      setCreatingProcedureFromTemplate(null)
    }
  }

  const handleExportTemplate = (template: ProcedureTemplate) => {
    // Note: We map code -> template when loading, but TypeScript doesn't know about it
    const templateCode = (template as any).template || template.code || ''
    const dataStr = JSON.stringify({
      name: template.name,
      description: template.description,
      template: templateCode,
      version: template.version || '1.0',
      category: template.category
    }, null, 2)

    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${template.name}-v${template.version || '1.0'}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-shrink-0 p-6 pb-4">
        <h1 className="text-3xl font-bold">Experiment Templates</h1>
        <p className="text-muted-foreground">
          Manage experiment templates that define state machine behavior for hypothesis generation.
          Click "Create Experiment" to start a new experiment using a template's configuration.
        </p>
      </div>

      <div className="flex-1 overflow-hidden px-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="browse">Browse Templates</TabsTrigger>
          <TabsTrigger value="create">Create Template</TabsTrigger>
        </TabsList>

        <TabsContent value="browse" className="flex-1 overflow-y-auto space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {isLoading ? (
              <div className="col-span-full text-center py-8">Loading templates...</div>
            ) : templates.length === 0 ? (
              <div className="col-span-full text-center py-8">
                <p className="text-muted-foreground">No templates found</p>
                <Button 
                  onClick={() => setActiveTab('create')} 
                  className="mt-4"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Create First Template
                </Button>
              </div>
            ) : (
              templates.map((template) => (
                <Card key={template.id} className="cursor-pointer hover:shadow-md transition-shadow">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{template.name}</CardTitle>
                        <CardDescription className="line-clamp-2">
                          {template.description || 'No description'}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-1">
                        {(template as any).isDefault && (
                          <Badge variant="default" className="text-xs">Default</Badge>
                        )}
                        <Badge variant="outline" className="text-xs">
                          v{(template as any).version || '1.0'}
                        </Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="text-sm text-muted-foreground">
                        Category: {template.category || 'Unknown'}
                      </div>
                      
                      <div className="flex items-center gap-2 flex-wrap">
                        <Button
                          size="sm"
                          onClick={() => handleCreateProcedureFromTemplate(template)}
                          disabled={creatingProcedureFromTemplate === template.id}
                        >
                          <Plus className="w-3 h-3 mr-1" />
                          {creatingProcedureFromTemplate === template.id ? 'Creating...' : 'Create Procedure'}
                        </Button>
                        
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleCopyTemplate(template)}
                        >
                          <Copy className="w-3 h-3 mr-1" />
                          Copy
                        </Button>
                        
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleExportTemplate(template)}
                        >
                          <Download className="w-3 h-3 mr-1" />
                          Export
                        </Button>
                        
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDeleteTemplate(template)}
                          disabled={(template as any).isDefault || false}
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        <TabsContent value="create" className="flex-1 overflow-y-auto space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Create New Template</CardTitle>
              <CardDescription>
                Define a new experiment template with custom state machine configuration
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Template Name *</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="e.g., Advanced Hypothesis Generation"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="version">Version *</Label>
                  <Input
                    id="version"
                    value={formData.version}
                    onChange={(e) => setFormData(prev => ({ ...prev, version: e.target.value }))}
                    placeholder="e.g., 1.0, 2.1"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Describe what this template is for and how it differs from others"
                  rows={3}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="category">Category</Label>
                  <Select
                    value={formData.category}
                    onValueChange={(value) => setFormData(prev => ({ ...prev, category: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="hypothesis_generation">Hypothesis Generation</SelectItem>
                      <SelectItem value="beam_search">Beam Search</SelectItem>
                      <SelectItem value="custom">Custom</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center space-x-2 pt-6">
                  <Switch
                    id="isDefault"
                    checked={formData.isDefault}
                    onCheckedChange={(checked) => setFormData(prev => ({ ...prev, isDefault: checked }))}
                  />
                  <Label htmlFor="isDefault">Set as default template</Label>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="template">Template YAML *</Label>
                <div className="border rounded-md overflow-hidden">
                  <Editor
                    height="400px"
                    defaultLanguage="yaml"
                    value={formData.template}
                    onChange={(value) => setFormData(prev => ({ ...prev, template: value || '' }))}
                    onMount={(editor, monaco) => {
                      defineCustomMonacoThemes(monaco)
                      applyMonacoTheme(monaco)
                      setupMonacoThemeWatcher(monaco)
                    }}
                    options={{
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      fontSize: 13,
                      wordWrap: 'on',
                      automaticLayout: true
                    }}
                  />
                </div>
              </div>

              <div className="flex gap-2">
                <Button onClick={handleCreateTemplate} disabled={isLoading}>
                  {isLoading ? 'Creating...' : 'Create Template'}
                </Button>
                <Button variant="outline" onClick={resetForm}>
                  Reset
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      </div>
    </div>
  )
}

"use client"
import React, { useState, useEffect, useCallback } from "react"
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
import ProcedureTask from "./ProcedureTask"
import GraphNodesList from "./graph-nodes-list"
import { useAccount } from '@/app/contexts/AccountContext'
import ScorecardContext from '@/components/ScorecardContext'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

// Types based on our GraphQL schema
type Procedure = Schema['Procedure']['type']

const client = generateClient<Schema>()

// Minimal fallback for YAML editor - actual templates come from backend service
const MINIMAL_YAML_FALLBACK = `class: "BeamSearch"
# Default procedure template will be loaded from backend...`

interface Props {
  procedureId?: string
  onSave?: () => void
  onCancel?: () => void
  initialEditMode?: boolean
}

export default function ProcedureDetail({ procedureId, onSave, onCancel, initialEditMode = false }: Props) {
  const router = useRouter()
  const { selectedAccount } = useAccount()
  
  const [procedure, setProcedure] = useState<Procedure | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isEditMode, setIsEditMode] = useState(initialEditMode)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Form fields
  const [featured, setFeatured] = useState(false)
  const [code, setCode] = useState('')
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  
  // YAML linting
  const { lintResult, isLinting, lint, setupMonacoIntegration, jumpToLine } = useYamlLinter({ context: 'experiment' })
  const handleLintMessage = useLintMessageHandler(jumpToLine)

  // Setup Monaco theme watcher
  useEffect(() => {
    // Monaco theme watcher will be setup in editor onMount
  }, [])

  useEffect(() => {
    if (procedureId) {
      loadProcedure()
    } else {
      // New procedure mode
      setIsLoading(false)
      setIsEditMode(true)
      setCode(MINIMAL_YAML_FALLBACK)
    }
  }, [procedureId])

  const loadProcedure = async () => {
    if (!procedureId) return
    
    try {
      setIsLoading(true)
      setError(null)
      
      const result = await client.graphql({
        query: `
          query GetProcedure($id: ID!) {
            getProcedure(id: $id) {
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
          }
        `,
        variables: { id: procedureId }
      })
      
      const fetchedProcedure = (result as any).data?.getProcedure
      if (fetchedProcedure) {
        setProcedure(fetchedProcedure)
        setFeatured(fetchedProcedure.featured || false)
        setCode(fetchedProcedure.code || MINIMAL_YAML_FALLBACK)
                      setSelectedScorecard(fetchedProcedure.scorecardId ?? null)
        setSelectedScore(fetchedProcedure.scoreId ?? null)
      } else {
        setError('Procedure not found')
      }
    } catch (err) {
      console.error('Error loading procedure:', err)
      setError(err instanceof Error ? err.message : 'Failed to load procedure')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSave = async () => {
    if (!selectedAccount?.id) {
      toast.error('No account selected')
      return
    }

    try {
      setIsSaving(true)
      
      if (procedureId) {
        // Update existing procedure
        await client.graphql({
          query: `
            mutation UpdateProcedure($input: UpdateProcedureInput!) {
              updateProcedure(input: $input) {
                id
                featured
                code
                scorecardId
                scoreId
                updatedAt
              }
            }
          `,
          variables: {
            input: {
              id: procedureId,
              featured,
              code: code || null,
              scorecardId: selectedScorecard || null,
              scoreId: selectedScore || null,
            }
          }
        })
        
        toast.success('Procedure updated successfully')
      } else {
        // Create new procedure
        const result = await client.graphql({
          query: `
            mutation CreateProcedure($input: CreateProcedureInput!) {
              createProcedure(input: $input) {
                id
                featured
                code
                scorecardId
                scoreId
                createdAt
                updatedAt
              }
            }
          `,
          variables: {
            input: {
              featured,
              code: code || null,
              scorecardId: selectedScorecard || null,
              scoreId: selectedScore || null,
              accountId: selectedAccount.id,
            }
          }
        })
        
        const newProcedure = (result as any).data?.createProcedure
        if (newProcedure) {
          toast.success('Procedure created successfully')
          router.push(`/lab/procedures/${newProcedure.id}`)
        }
      }
      
      setIsEditMode(false)
      if (onSave) {
        onSave()
      }
    } catch (error) {
      console.error('Error saving procedure:', error)
      toast.error('Failed to save procedure')
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    if (procedure) {
      // Reset to original values
      setFeatured(procedure.featured || false)
      setCode(procedure.code || MINIMAL_YAML_FALLBACK)
      setSelectedScorecard(procedure.scorecardId ?? null)
      setSelectedScore(procedure.scoreId ?? null)
    }
    setIsEditMode(false)
    if (onCancel) {
      onCancel()
    }
  }

  const handleDelete = async () => {
    if (!procedureId || !window.confirm('Are you sure you want to delete this procedure?')) {
      return
    }

    try {
      await client.graphql({
        query: `
          mutation DeleteProcedure($input: DeleteProcedureInput!) {
            deleteProcedure(input: $input) {
              id
            }
          }
        `,
        variables: {
          input: { id: procedureId }
        }
      })
      
      toast.success('Procedure deleted successfully')
      router.push('/lab/procedures')
    } catch (error) {
      console.error('Error deleting procedure:', error)
      toast.error('Failed to delete procedure')
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p>Loading procedure...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center text-destructive p-8">
        <p>Error: {error}</p>
        <Button onClick={() => router.push('/lab/procedures')} variant="outline" className="mt-4">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Procedures
        </Button>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push('/lab/procedures')}
              className="h-8 w-8"
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <Waypoints className="h-5 w-5 text-primary" />
            <div>
              <h1 className="text-xl font-semibold">
                {procedureId ? 'Edit Procedure' : 'New Procedure'}
              </h1>
              {procedure && (
                <p className="text-sm text-muted-foreground">
                  {procedure.scorecard?.name} - {procedure.score?.name}
                </p>
              )}
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {isEditMode ? (
              <>
                <Button onClick={handleCancel} variant="outline" disabled={isSaving}>
                  Cancel
                </Button>
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? 'Saving...' : 'Save'}
                </Button>
              </>
            ) : (
              <>
                <Button onClick={() => setIsEditMode(true)} variant="outline">
                  Edit
                </Button>
                {procedureId && (
                  <Button onClick={handleDelete} variant="destructive">
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {isEditMode ? (
          <>
            {/* Edit Form */}
            <Card>
              <CardContent className="p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="featured">Featured</Label>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="featured"
                        checked={featured}
                        onCheckedChange={setFeatured}
                      />
                      <Label htmlFor="featured" className="text-sm text-muted-foreground">
                        Mark as featured procedure
                      </Label>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Scorecard & Score</Label>
                  <ScorecardContext
                    selectedScorecard={selectedScorecard}
                    setSelectedScorecard={setSelectedScorecard}
                    selectedScore={selectedScore}
                    setSelectedScore={setSelectedScore}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="code">Configuration (YAML)</Label>
                  <div className="border rounded-md overflow-hidden">
                    <Editor
                      height="400px"
                      defaultLanguage="yaml"
                      value={code}
                      onChange={(value) => {
                        setCode(value || '')
                        lint(value || '')
                      }}
                      options={getCommonMonacoOptions()}
                      onMount={(editorInstance, monaco) => {
                        defineCustomMonacoThemes(monaco)
                        applyMonacoTheme(monaco)
                        configureYamlLanguage(monaco)
                        setupMonacoIntegration(editorInstance, monaco)
                      }}
                    />
                  </div>
                  {lintResult?.messages && lintResult.messages.length > 0 && (
                    <YamlLinterPanel result={lintResult} onMessageClick={handleLintMessage} />
                  )}
                </div>
              </CardContent>
            </Card>
          </>
        ) : (
          <>
            {/* View Mode */}
            {procedure && (
              <ProcedureTask
                variant="detail"
                procedure={{
                  id: procedure.id,
                  title: `${procedure.scorecard?.name || 'Procedure'} - ${procedure.score?.name || 'Score'}`,
                  featured: procedure.featured || false,
                  rootNodeId: procedure.rootNodeId || undefined,
                  createdAt: procedure.createdAt,
                  updatedAt: procedure.updatedAt,
                  scorecard: procedure.scorecard ? { name: procedure.scorecard.name } : null,
                  score: procedure.score ? { name: procedure.score.name } : null,
                }}
              />
            )}

            {/* Graph Nodes */}
            {procedureId && (
              <Accordion type="single" collapsible>
                <AccordionItem value="nodes">
                  <AccordionTrigger>
                    <div className="flex items-center gap-2">
                      <Waypoints className="h-4 w-4" />
                      <span>Graph Nodes</span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="bg-background rounded-lg p-4">
                    <GraphNodesList procedureId={procedureId} />
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            )}
          </>
        )}
      </div>
    </div>
  )
}

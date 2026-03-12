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
import { Trash2, Waypoints, FileText, ChevronRight, ChevronDown, ArrowLeft } from "lucide-react"
import { Timestamp } from "./ui/timestamp"
import { toast } from "sonner"
import Editor from "@monaco-editor/react"
import { useYamlLinter, useLintMessageHandler } from "@/hooks/use-yaml-linter"
import YamlLinterPanel from "@/components/ui/yaml-linter-panel"
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions, configureYamlLanguage } from "@/lib/monaco-theme"
import ProcedureTask from "./ProcedureTask"
import GraphNodesList from "./graph-nodes-list"
import { useAccount } from '@/app/contexts/AccountContext'
import ScorecardContext from '@/components/ScorecardContext'
import { ConfigurableParametersForm } from "@/components/ui/ConfigurableParametersForm"
import { ParametersDisplay } from "@/components/ui/ParametersDisplay"
import { parseParametersFromYaml } from "@/lib/parameter-parser"
import type { ParameterDefinition, ParameterValue } from "@/types/parameters"
import { CardButton } from "@/components/CardButton"
import { X } from "lucide-react"

type ParameterValues = ParameterValue
import * as yaml from 'js-yaml'
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

export default function ProcedureTaskEdit({ procedureId, onSave, onCancel, initialEditMode = false }: Props) {
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
  
  // Parameters
  const [parameters, setParameters] = useState<ParameterDefinition[]>([])
  const [parameterValues, setParameterValues] = useState<ParameterValues>({})
  const [parameterErrors, setParameterErrors] = useState<Record<string, string>>({})
  
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

  // Parse parameters from code whenever code changes
  useEffect(() => {
    if (code) {
      try {
        const parsedParams = parseParametersFromYaml(code)
        setParameters(parsedParams)
        
        // Extract values from the YAML
        const config = yaml.load(code) as any
        if (config && config.parameters && Array.isArray(config.parameters)) {
          const values: ParameterValues = {}
          config.parameters.forEach((param: any) => {
            if (param.value !== undefined) {
              values[param.name] = param.value
            }
          })
          setParameterValues(values)
        }
      } catch (error) {
        console.error('Error parsing parameters from code:', error)
        setParameters([])
        setParameterValues({})
      }
    }
  }, [code])

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

  const injectParameterValuesIntoCode = (codeStr: string, values: ParameterValues): string => {
    try {
      const config = yaml.load(codeStr) as any
      if (config && config.parameters && Array.isArray(config.parameters)) {
        config.parameters = config.parameters.map((param: any) => ({
          ...param,
          value: values[param.name] !== undefined ? values[param.name] : param.value
        }))
        return yaml.dump(config)
      }
      return codeStr
    } catch (error) {
      console.error('Error injecting parameter values:', error)
      return codeStr
    }
  }

  const handleSave = async () => {
    if (!selectedAccount?.id) {
      toast.error('No account selected')
      return
    }

    // Validate required parameters
    const errors: Record<string, string> = {}
    parameters.forEach(param => {
      if (param.required && !parameterValues[param.name]) {
        errors[param.name] = `${param.label} is required`
      }
    })

    if (Object.keys(errors).length > 0) {
      setParameterErrors(errors)
      toast.error('Please fill in all required parameters')
      return
    }

    try {
      setIsSaving(true)
      
      // Inject parameter values into code
      const codeWithValues = injectParameterValuesIntoCode(code, parameterValues)
      
      if (procedureId) {
        // Update existing procedure
        // Note: scoreVersionId is stored in the YAML code, not as a separate field
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
              code: codeWithValues || null,
              scorecardId: parameterValues.scorecard_id || selectedScorecard || null,
              scoreId: parameterValues.score_id || selectedScore || null,
            }
          }
        })
        
        toast.success('Procedure updated successfully')
      } else {
        // Create new procedure
        // Note: scoreVersionId is stored in the YAML code, not as a separate field
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
              code: codeWithValues || null,
              scorecardId: parameterValues.scorecard_id || selectedScorecard || null,
              scoreId: parameterValues.score_id || selectedScore || null,
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
      // Log the detailed error if it's a GraphQL error
      if ((error as any).errors && Array.isArray((error as any).errors)) {
        (error as any).errors.forEach((err: any, index: number) => {
          console.error(`GraphQL Error ${index + 1}:`, {
            message: err.message,
            errorType: err.errorType,
            errorInfo: err.errorInfo,
            path: err.path,
            locations: err.locations
          })
        })
      }
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
    <div className="h-full flex flex-col bg-card rounded-lg w-full max-w-full">
      {/* Header - similar to ProcedureTask detail header */}
      <div className="flex-none p-3 w-full max-w-full overflow-hidden">
        <div className="space-y-1.5 p-0 flex flex-col items-start w-full max-w-full px-1">
          <div className="flex justify-between items-start w-full max-w-full gap-3 overflow-hidden">
            <div className="flex flex-col pb-1 leading-none min-w-0 flex-1 overflow-hidden">
              <div className="flex items-center gap-2 mb-1">
                <Waypoints className="h-5 w-5 text-muted-foreground" />
                <span className="text-lg font-semibold text-muted-foreground">Procedure</span>
              </div>
              
              {/* Timestamp */}
              {procedure && (
                <div className="mb-1">
                  <Timestamp time={procedure.updatedAt} variant="relative" />
                </div>
              )}
            </div>
            
            <div className="flex flex-col items-end flex-shrink-0 gap-2">
              <div className="flex gap-2">
                {isEditMode ? (
                  <CardButton
                    icon={X}
                    onClick={handleCancel}
                    disabled={isSaving}
                    aria-label="Cancel"
                  />
                ) : (
                  <>
                    {onCancel && (
                      <CardButton
                        icon={X}
                        onClick={onCancel}
                        aria-label="Close"
                      />
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content - similar to ProcedureTask content structure */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="p-3">
          {/* Parameters section */}
          {isEditMode ? (
            parameters.length > 0 ? (
              <div className="mb-4 w-full">
                <ConfigurableParametersForm
                  parameters={parameters}
                  values={parameterValues}
                  onChange={setParameterValues}
                  errors={parameterErrors}
                />
              </div>
            ) : (
              <div className="mb-4 w-full max-w-sm">
                <ScorecardContext
                  selectedScorecard={selectedScorecard}
                  setSelectedScorecard={setSelectedScorecard}
                  selectedScore={selectedScore}
                  setSelectedScore={setSelectedScore}
                />
              </div>
            )
          ) : (
            parameters.length > 0 ? (
              <div className="mb-4 w-full">
                <ParametersDisplay
                  parameters={parameters}
                  values={parameterValues}
                  variant="table"
                />
              </div>
            ) : (
              <>
                {procedure?.scorecard && (
                  <div className="text-sm text-muted-foreground mb-2">{procedure.scorecard.name}</div>
                )}
                {procedure?.score && (
                  <div className="text-sm text-muted-foreground mb-4">{procedure.score.name}</div>
                )}
              </>
            )
          )}

          {/* Configuration section */}
          <Accordion type="multiple" defaultValue={isEditMode ? ["configuration"] : []} className="w-full">
            <AccordionItem value="configuration" className="border-b-0">
              <AccordionTrigger className="hover:no-underline py-2 px-0 justify-start [&>svg]:hidden group">
                <div className="flex items-center gap-2">
                  <FileText className="h-3 w-3 text-muted-foreground" />
                  <span className="text-sm font-medium leading-none text-muted-foreground">Code</span>
                  <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform duration-200 group-data-[state=open]:hidden" />
                  <ChevronDown className="h-3 w-3 text-muted-foreground transition-transform duration-200 hidden group-data-[state=open]:block" />
                </div>
              </AccordionTrigger>
              <AccordionContent className="pt-0 pb-4">
                <div className="overflow-hidden">
                  <Editor
                    height="400px"
                    defaultLanguage="yaml"
                    value={code}
                    onChange={isEditMode ? (value) => {
                      setCode(value || '')
                      lint(value || '')
                    } : undefined}
                    onMount={(editorInstance, monaco) => {
                      defineCustomMonacoThemes(monaco)
                      applyMonacoTheme(monaco)
                      setupMonacoThemeWatcher(monaco)
                      configureYamlLanguage(monaco)
                      if (isEditMode) {
                        setupMonacoIntegration(editorInstance, monaco)
                      }
                    }}
                    options={{
                      ...getCommonMonacoOptions(),
                      readOnly: !isEditMode,
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      wordWrap: 'on',
                      tabSize: 2,
                      insertSpaces: true,
                    }}
                  />
                  {isEditMode && lintResult?.messages && lintResult.messages.length > 0 && (
                    <div className="mt-2">
                      <YamlLinterPanel result={lintResult} onMessageClick={handleLintMessage} />
                    </div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>


          {/* Procedure Nodes section - only show when not in edit mode and procedureId exists */}
          {!isEditMode && procedureId && (
            <div className="mt-6 bg-background rounded-lg p-4">
              <GraphNodesList procedureId={procedureId} />
            </div>
          )}
        </div>
        
        {/* Save/Cancel Bar - appears when in edit mode */}
        {isEditMode && (
          <div className="mt-3">
            <div className="flex items-center gap-3 bg-muted/50 rounded-lg p-3">
              <Button
                variant="secondary"
                onClick={handleCancel}
                disabled={isSaving}
                className="shrink-0 h-10"
              >
                Cancel
              </Button>
              <div className="flex-1" /> {/* Spacer to push Save button to the right */}
              <Button
                variant="default"
                onClick={handleSave}
                disabled={isSaving}
                className="shrink-0 h-10"
              >
                {isSaving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

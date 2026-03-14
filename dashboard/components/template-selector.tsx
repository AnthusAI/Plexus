"use client"

import React, { useState, useEffect } from 'react'
import { generateClient } from 'aws-amplify/data'
import type { Schema } from '@/amplify/data/resource'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ConfigurableParametersDialog } from '@/components/ui/ConfigurableParametersDialog'
import { Sparkles, Beaker, FileCode2 } from 'lucide-react'
import { toast } from 'sonner'
import { parseParametersFromYaml } from '@/lib/parameter-parser'

const client = generateClient<Schema>()

type ProcedureTemplate = Schema['Procedure']['type']

type BuiltInProcedureTemplate = {
  slug: string
  name: string
  description: string
  category: string
  version: string
  code: string
}

interface TemplateSelectorProps {
  accountId: string
  accountName?: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onTemplateSelect: (template: ProcedureTemplate, parameters?: Record<string, any>) => void
}

export default function TemplateSelector({ accountId, accountName, open, onOpenChange, onTemplateSelect }: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<ProcedureTemplate[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [creatingProcedureFromTemplate, setCreatingProcedureFromTemplate] = useState<string | null>(null)
  const [showParametersDialog, setShowParametersDialog] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<ProcedureTemplate | null>(null)

  useEffect(() => {
    if (open) {
      loadTemplates()
    }
  }, [open, accountId])

  const listAccountProcedures = async () => {
    const result = await client.graphql({
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
              isTemplate
              category
              version
              isDefault
              createdAt
              updatedAt
            }
            nextToken
          }
        }
      `,
      variables: {
        accountId,
        sortDirection: 'DESC',
        limit: 100,
      }
    })

    return (result as any).data?.listProcedureByAccountIdAndUpdatedAt?.items || []
  }

  const getProcedureTemplateDetails = async (procedureId: string) => {
    const result = await client.graphql({
      query: `
        query GetProcedure($id: ID!) {
          getProcedure(id: $id) {
            id
            name
            description
            code
            isTemplate
            category
            version
            isDefault
            accountId
            createdAt
            updatedAt
          }
        }
      `,
      variables: { id: procedureId },
    })

    return (result as any).data?.getProcedure || null
  }

  const ensureBuiltInTemplates = async () => {
    const response = await fetch('/api/procedure-templates/builtin', {
      cache: 'no-store',
    })

    if (!response.ok) {
      throw new Error('Failed to load built-in procedure templates')
    }

    const payload = await response.json()
    const builtInTemplates = (payload.templates || []) as BuiltInProcedureTemplate[]
    if (builtInTemplates.length === 0) {
      return
    }

    const existingProcedures = await listAccountProcedures()
    const existingTemplates = existingProcedures.filter((procedure: any) => procedure.isTemplate === true)

    for (const builtInTemplate of builtInTemplates) {
      const existingTemplate = existingTemplates.find(
        (template: any) =>
          template.category === builtInTemplate.category
      )

      if (existingTemplate) {
        let existingTemplateDetails: any = null
        try {
          existingTemplateDetails = await getProcedureTemplateDetails(existingTemplate.id)
        } catch (error) {
          console.warn('Failed to load template details for built-in comparison:', existingTemplate.id, error)
        }

        const existingCode = (existingTemplateDetails?.code || '') as string
        const needsUpdate =
          existingTemplate.isTemplate !== true ||
          existingTemplate.version !== builtInTemplate.version ||
          existingTemplateDetails?.name !== builtInTemplate.name ||
          existingTemplateDetails?.description !== builtInTemplate.description ||
          existingCode !== builtInTemplate.code

        if (needsUpdate) {
          await client.graphql({
            query: `
              mutation UpdateProcedure($input: UpdateProcedureInput!) {
                updateProcedure(input: $input) {
                  id
                }
              }
            `,
            variables: {
              input: {
                id: existingTemplate.id,
                name: builtInTemplate.name,
                description: builtInTemplate.description,
                code: builtInTemplate.code,
                category: builtInTemplate.category,
                version: builtInTemplate.version,
                isTemplate: true,
                isDefault: false,
              },
            },
          })
        }

        continue
      }

      await client.graphql({
        query: `
          mutation CreateProcedure($input: CreateProcedureInput!) {
            createProcedure(input: $input) {
              id
            }
          }
        `,
        variables: {
          input: {
            accountId,
            name: builtInTemplate.name,
            description: builtInTemplate.description,
            code: builtInTemplate.code,
            category: builtInTemplate.category,
            version: builtInTemplate.version,
            isTemplate: true,
            isDefault: false,
            featured: false,
          },
        },
      })
    }
  }

  const loadTemplates = async () => {
    setIsLoading(true)
    try {
      await ensureBuiltInTemplates()
      const allProcedures = await listAccountProcedures()
      const templateCandidates = allProcedures.filter((procedure: any) => procedure.isTemplate === true)
      const templateDetails = await Promise.all(
        templateCandidates.map(async (procedure: any) => {
          try {
            return await getProcedureTemplateDetails(procedure.id)
          } catch (error) {
            console.warn('Skipping template with invalid data:', procedure.id, error)
            return null
          }
        })
      )

      const templatesData = templateDetails
        .filter((procedure: any) => procedure?.isTemplate === true)
        .map((procedure: any) => ({ ...procedure, template: procedure.code }))
        .sort((a: any, b: any) => {
          if (a.isDefault && !b.isDefault) return -1
          if (!a.isDefault && b.isDefault) return 1
          return a.name.localeCompare(b.name)
        })

      setTemplates(templatesData)
    } catch (error) {
      console.error('Error loading templates:', error)
      toast.error("Failed to load runnable procedures")
    } finally {
      setIsLoading(false)
    }
  }

  const handleRunProcedureFromTemplate = async (template: ProcedureTemplate) => {
    const templateCode = (template as any).template || template.code || ''
    const parameters = parseParametersFromYaml(templateCode)
    const visibleParameters = parameters.filter((parameter) => parameter.input !== 'hidden')

    if (visibleParameters.length > 0) {
      setSelectedTemplate(template)
      setShowParametersDialog(true)
    } else {
      setCreatingProcedureFromTemplate(template.id)
      try {
        await onTemplateSelect(template)
      } finally {
        setCreatingProcedureFromTemplate(null)
      }
    }
  }

  const handleParametersSubmit = async (parameters: Record<string, any>) => {
    if (!selectedTemplate) return
    
    setCreatingProcedureFromTemplate(selectedTemplate.id)
    setShowParametersDialog(false)
    
    try {
      await onTemplateSelect(selectedTemplate, parameters)
    } finally {
      setCreatingProcedureFromTemplate(null)
      setSelectedTemplate(null)
    }
  }

  const selectedTemplateParameters = selectedTemplate
    ? parseParametersFromYaml((selectedTemplate as any).template || selectedTemplate.code || '')
    : []
  const selectedTemplateDescription = selectedTemplateParameters.some(
    (parameter) => parameter.name === 'account_identifier' && parameter.input === 'hidden'
  ) && accountName
    ? `Runs in account: ${accountName}`
    : 'Please provide the required parameters for this procedure template'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileCode2 className="h-5 w-5" />
            Run Procedure
          </DialogTitle>
          <DialogDescription>
            Select a procedure template to create and start a new run.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="text-center py-12">
              <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4" />
              <p className="text-muted-foreground">Loading procedures...</p>
            </div>
          ) : templates.length === 0 ? (
            <div className="text-center py-12">
              <Beaker className="h-16 w-16 text-muted-foreground mx-auto mb-6 opacity-50" />
              <h3 className="text-lg font-medium mb-2">No runnable procedures available</h3>
              <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                Built-in and saved procedure templates will appear here when available.
              </p>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Close
              </Button>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {templates.map((template) => (
                <Card 
                  key={template.id} 
                  className="relative group cursor-pointer border border-border bg-card hover:shadow-md transition-all duration-200 hover:border-primary/30"
                  onClick={() => handleRunProcedureFromTemplate(template)}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <Beaker className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          <span className="text-xs font-medium text-muted-foreground">Template</span>
                        </div>
                        <h4 className="font-semibold text-sm leading-tight truncate mb-1">
                          {template.name}
                        </h4>
                        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                          {template.description || 'No description provided'}
                        </p>
                      </div>
                    </div>
                  </CardHeader>
                  
                  <CardContent className="pt-0">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        {template.isDefault && (
                          <Badge variant="default" className="text-xs">Default</Badge>
                        )}
                        <Badge variant="outline" className="text-xs">
                          v{template.version}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {template.category || 'Unknown'}
                      </div>
                    </div>
                    
                    <Button
                      size="sm"
                      className="w-full"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleRunProcedureFromTemplate(template)
                      }}
                      disabled={creatingProcedureFromTemplate === template.id}
                    >
                      {creatingProcedureFromTemplate === template.id ? (
                        <>
                          <div className="animate-spin h-3 w-3 border border-current border-t-transparent rounded-full mr-2" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3 h-3 mr-2" />
                          Run Procedure
                        </>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </DialogContent>

      {selectedTemplate && (
        <ConfigurableParametersDialog
          open={showParametersDialog}
          onOpenChange={(isOpen) => {
            setShowParametersDialog(isOpen)
            if (!isOpen) setSelectedTemplate(null)
          }}
          title={`Configure ${selectedTemplate.name}`}
          description={selectedTemplateDescription}
          parameters={selectedTemplateParameters}
          onSubmit={handleParametersSubmit}
          submitLabel="Create And Run"
        />
      )}
    </Dialog>
  )
}

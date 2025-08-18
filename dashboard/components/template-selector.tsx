"use client"

import React, { useState, useEffect } from 'react'
import { generateClient } from 'aws-amplify/data'
import type { Schema } from '@/amplify/data/resource'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Sparkles, Beaker, FileCode2 } from 'lucide-react'
import { toast } from 'sonner'

const client = generateClient<Schema>()

// Types
type ExperimentTemplate = Schema['ExperimentTemplate']['type']

interface TemplateSelectorProps {
  accountId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onTemplateSelect: (template: ExperimentTemplate) => void
}

export default function TemplateSelector({ accountId, open, onOpenChange, onTemplateSelect }: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<ExperimentTemplate[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [creatingExperimentFromTemplate, setCreatingExperimentFromTemplate] = useState<string | null>(null)

  // Load templates when dialog opens
  useEffect(() => {
    if (open) {
      loadTemplates()
    }
  }, [open, accountId])

  const loadTemplates = async () => {
    setIsLoading(true)
    try {
      const result = await (client.models.ExperimentTemplate.listExperimentTemplateByAccountIdAndUpdatedAt as any)({
        accountId: accountId
      })
      
      if (result.data) {
        setTemplates(result.data)
      }
    } catch (error) {
      console.error('Error loading templates:', error)
      toast.error("Failed to load experiment templates")
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreateExperimentFromTemplate = async (template: ExperimentTemplate) => {
    setCreatingExperimentFromTemplate(template.id)
    try {
      await onTemplateSelect(template)
    } finally {
      setCreatingExperimentFromTemplate(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileCode2 className="h-5 w-5" />
            Choose Experiment Template
          </DialogTitle>
          <DialogDescription>
            Select a template to create a new experiment with predefined configuration.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="text-center py-12">
              <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-4" />
              <p className="text-muted-foreground">Loading templates...</p>
            </div>
          ) : templates.length === 0 ? (
            <div className="text-center py-12">
              <Beaker className="h-16 w-16 text-muted-foreground mx-auto mb-6 opacity-50" />
              <h3 className="text-lg font-medium mb-2">No templates available</h3>
              <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                Templates can be created and managed in the Templates dashboard.
              </p>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Go to Templates Dashboard
              </Button>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {templates.map((template) => (
                <Card 
                  key={template.id} 
                  className="relative group cursor-pointer border border-border bg-card hover:shadow-md transition-all duration-200 hover:border-primary/30"
                  onClick={() => handleCreateExperimentFromTemplate(template)}
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
                        handleCreateExperimentFromTemplate(template)
                      }}
                      disabled={creatingExperimentFromTemplate === template.id}
                    >
                      {creatingExperimentFromTemplate === template.id ? (
                        <>
                          <div className="animate-spin h-3 w-3 border border-current border-t-transparent rounded-full mr-2" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3 h-3 mr-2" />
                          Use Template
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
    </Dialog>
  )
}
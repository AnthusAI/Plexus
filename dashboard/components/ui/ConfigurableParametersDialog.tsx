"use client"

import React, { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AlertCircle } from 'lucide-react'
import { ParameterDefinition, ParameterValue } from '@/types/parameters'
import { validateParameters, getDefaultValues } from '@/lib/parameter-parser'
import {
  TextParameter,
  NumberParameter,
  BooleanParameter,
  SelectParameter,
  ScorecardSelectParameter,
  ScoreSelectParameter,
  ScoreVersionSelectParameter,
} from './parameter-types'

export interface ConfigurableParametersDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  parameters: ParameterDefinition[]
  onSubmit: (values: ParameterValue) => void | Promise<void>
  submitLabel?: string
  cancelLabel?: string
}

export function ConfigurableParametersDialog({
  open,
  onOpenChange,
  title,
  description,
  parameters,
  onSubmit,
  submitLabel = 'Submit',
  cancelLabel = 'Cancel',
}: ConfigurableParametersDialogProps) {
  const [values, setValues] = useState<ParameterValue>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Initialize with default values when dialog opens or parameters change
  useEffect(() => {
    if (open) {
      const defaults = getDefaultValues(parameters)
      setValues(defaults)
      setErrors({})
    }
  }, [open, parameters])

  const handleValueChange = (name: string, value: any) => {
    setValues(prev => ({ ...prev, [name]: value }))
    
    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev }
        delete newErrors[name]
        return newErrors
      })
    }

    // Clear dependent fields when a dependency changes
    const dependentParams = parameters.filter(p => p.depends_on === name)
    if (dependentParams.length > 0) {
      setValues(prev => {
        const newValues = { ...prev }
        dependentParams.forEach(p => {
          newValues[p.name] = ''
        })
        return newValues
      })
    }
  }

  const handleSubmit = async () => {
    // Validate
    const validation = validateParameters(values, parameters)
    
    if (!validation.valid) {
      const errorMap: Record<string, string> = {}
      validation.errors.forEach(err => {
        errorMap[err.parameter] = err.message
      })
      setErrors(errorMap)
      return
    }

    // Submit
    setIsSubmitting(true)
    try {
      await onSubmit(values)
      onOpenChange(false)
    } catch (error) {
      console.error('Error submitting parameters:', error)
      // Keep dialog open on error
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderParameter = (param: ParameterDefinition) => {
    const value = values[param.name]
    const error = errors[param.name]
    const onChange = (val: any) => handleValueChange(param.name, val)

    switch (param.type) {
      case 'text':
        return <TextParameter key={param.name} definition={param} value={value} onChange={onChange} error={error} />

      case 'number':
        return <NumberParameter key={param.name} definition={param} value={value} onChange={onChange} error={error} />

      case 'boolean':
        return <BooleanParameter key={param.name} definition={param} value={value} onChange={onChange} error={error} />

      case 'select':
        return <SelectParameter key={param.name} definition={param} value={value} onChange={onChange} error={error} />

      case 'scorecard_select':
        return <ScorecardSelectParameter key={param.name} definition={param} value={value} onChange={onChange} error={error} />

      case 'score_select':
        const scorecardId = param.depends_on ? values[param.depends_on] : undefined
        return <ScoreSelectParameter key={param.name} definition={param} value={value} onChange={onChange} scorecardId={scorecardId} error={error} />

      case 'score_version_select':
        const scoreId = param.depends_on ? values[param.depends_on] : undefined
        return <ScoreVersionSelectParameter key={param.name} definition={param} value={value} onChange={onChange} scoreId={scoreId} error={error} />

      default:
        return (
          <Alert key={param.name} variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Unknown parameter type: {param.type}
            </AlertDescription>
          </Alert>
        )
    }
  }

  const hasErrors = Object.keys(errors).length > 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>

        <div className="space-y-6 py-4">
          {parameters.map(renderParameter)}
        </div>

        {hasErrors && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Please fix the errors above before submitting.
            </AlertDescription>
          </Alert>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            {cancelLabel}
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <div className="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full mr-2" />
                Submitting...
              </>
            ) : (
              submitLabel
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}




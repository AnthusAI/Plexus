"use client"

import React, { useState, useEffect } from 'react'
import type { ParameterDefinition, ParameterValue } from '@/types/parameters'

type ParameterValues = ParameterValue
import {
  TextParameter,
  NumberParameter,
  BooleanParameter,
  SelectParameter,
  ScorecardSelectParameter,
  ScoreSelectParameter,
  ScoreVersionSelectParameter,
} from './parameter-types'

interface ConfigurableParametersFormProps {
  parameters: ParameterDefinition[]
  values: ParameterValues
  onChange: (values: ParameterValues) => void
  errors?: Record<string, string>
}

export function ConfigurableParametersForm({
  parameters,
  values,
  onChange,
  errors = {}
}: ConfigurableParametersFormProps) {
  const [parameterValues, setParameterValues] = useState<ParameterValues>(values)

  useEffect(() => {
    setParameterValues(values)
  }, [values])

  const handleValueChange = (name: string, value: any) => {
    const newValues = { ...parameterValues, [name]: value }
    
    // Find parameter definition to check for dependencies
    const param = parameters.find(p => p.name === name)
    
    // Clear dependent fields when a parameter they depend on changes
    if (param) {
      parameters.forEach(p => {
        if (p.depends_on === name && newValues[p.name]) {
          newValues[p.name] = undefined
        }
      })
    }
    
    setParameterValues(newValues)
    onChange(newValues)
  }

  const isParameterEnabled = (param: ParameterDefinition): boolean => {
    if (!param.depends_on) return true
    
    const dependencyValue = parameterValues[param.depends_on]
    return dependencyValue !== undefined && dependencyValue !== null && dependencyValue !== ''
  }

  const renderParameter = (param: ParameterDefinition) => {
    const isEnabled = isParameterEnabled(param)
    const value = parameterValues[param.name]
    const error = errors[param.name]

    const commonProps = {
      definition: param,
      value,
      onChange: (newValue: any) => handleValueChange(param.name, newValue),
      disabled: !isEnabled,
      error
    }

    switch (param.type) {
      case 'text':
        return <TextParameter {...commonProps} />
      case 'number':
        return <NumberParameter {...commonProps} />
      case 'boolean':
        return <BooleanParameter {...commonProps} />
      case 'select':
        return <SelectParameter {...commonProps} />
      case 'scorecard_select':
        return <ScorecardSelectParameter {...commonProps} />
      case 'score_select':
        return <ScoreSelectParameter {...commonProps} scorecardId={param.depends_on ? parameterValues[param.depends_on] : undefined} />
      case 'score_version_select':
        // For score version, we need to find the score_select parameter it depends on
        const scoreParam = parameters.find(p => p.type === 'score_select')
        const scoreId = scoreParam ? parameterValues[scoreParam.name] : undefined
        return <ScoreVersionSelectParameter {...commonProps} scoreId={scoreId} />
      case 'date':
        return <TextParameter {...commonProps} />
      default:
        return <TextParameter {...commonProps} />
    }
  }

  if (parameters.length === 0) {
    return null
  }

  return (
    <div className="space-y-4">
      {parameters.map((param) => (
        <div key={param.name} className="space-y-2">
          {renderParameter(param)}
        </div>
      ))}
    </div>
  )
}


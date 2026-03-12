/**
 * Type definitions for configurable parameters system
 */

export type ParameterType = 
  | 'text'
  | 'number'
  | 'boolean'
  | 'select'
  | 'date'
  | 'scorecard_select'
  | 'score_select'
  | 'score_version_select'

export interface ParameterOption {
  value: string
  label: string
}

export interface ParameterDefinition {
  name: string
  label: string
  type: ParameterType
  required?: boolean
  default?: any
  options?: ParameterOption[]
  depends_on?: string
  description?: string
  placeholder?: string
  min?: number
  max?: number
}

export interface ParameterValue {
  [key: string]: any
}

export interface ParameterConfig {
  parameters?: ParameterDefinition[]
}

export interface ParameterValidationError {
  parameter: string
  message: string
}




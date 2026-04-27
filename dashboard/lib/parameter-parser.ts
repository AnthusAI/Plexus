/**
 * Utilities for parsing parameter definitions from YAML
 */

import yaml from 'js-yaml'
import { ParameterConfig, ParameterDefinition, DateRangeValue } from '@/types/parameters'

type RawParameterType = 'string' | 'text' | 'number' | 'boolean' | 'select' | 'date' | 'date_range' | string

function toTitleCase(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function normalizeParameterType(type: RawParameterType): ParameterDefinition['type'] {
  if (type === 'string') return 'text'
  if (type === 'text') return 'text'
  if (type === 'number') return 'number'
  if (type === 'boolean') return 'boolean'
  if (type === 'select') return 'select'
  if (type === 'date') return 'date'
  if (type === 'date_range') return 'date_range'
  return 'text'
}

function normalizeParameterDefinition(name: string, raw: any): ParameterDefinition {
  const type = normalizeParameterType(raw?.type || 'text')
  const input = raw?.input === 'textarea' || raw?.input === 'hidden' || raw?.input === 'text'
    ? raw.input
    : undefined
  const rows = typeof raw?.rows === 'number' ? raw.rows : undefined
  return {
    name,
    label: raw?.label || toTitleCase(name),
    type,
    input: type === 'text' ? input : undefined,
    rows: type === 'text' ? rows : undefined,
    required: Boolean(raw?.required),
    default: raw?.default,
    options: Array.isArray(raw?.options) ? raw.options : undefined,
    depends_on: typeof raw?.depends_on === 'string' ? raw.depends_on : undefined,
    description: typeof raw?.description === 'string' ? raw.description : undefined,
    placeholder: typeof raw?.placeholder === 'string' ? raw.placeholder : undefined,
    min: typeof raw?.min === 'number' ? raw.min : undefined,
    max: typeof raw?.max === 'number' ? raw.max : undefined,
  }
}

function extractDefinitionsFromParsedConfig(
  config: ParameterConfig & { params?: Record<string, any> } | undefined
): ParameterDefinition[] {
  if (Array.isArray(config?.parameters)) {
    return config.parameters
  }
  if (config?.params && typeof config.params === 'object') {
    return Object.entries(config.params).map(([name, raw]) => normalizeParameterDefinition(name, raw))
  }
  return []
}

/**
 * Extract parameter definitions from YAML content
 * Supports frontmatter format: parameters section before --- separator
 */
export function parseParametersFromYaml(yamlContent: string): ParameterDefinition[] {
  try {
    // Support "YAML header + --- + markdown body" templates used by reports.
    // We only treat the section before the first line containing exactly '---'
    // as candidate parameter config; everything after can be markdown/code fences.
    const separatorMatch = yamlContent.match(/^\s*---\s*$/m)
    if (separatorMatch && separatorMatch.index !== undefined) {
      const header = yamlContent.slice(0, separatorMatch.index).trim()
      if (header) {
        const parsedHeader = yaml.load(header) as ParameterConfig & { params?: Record<string, any> }
        const headerDefinitions = extractDefinitionsFromParsedConfig(parsedHeader)
        if (headerDefinitions.length > 0) {
          return headerDefinitions
        }
      }
    }

    // Parse the full YAML document
    const config = yaml.load(yamlContent) as ParameterConfig & { params?: Record<string, any> }
    return extractDefinitionsFromParsedConfig(config)
  } catch (error) {
    console.error('Error parsing parameters from YAML:', error)
    return []
  }
}

/**
 * Check if YAML content contains parameter definitions
 */
export function hasParameters(yamlContent: string): boolean {
  const params = parseParametersFromYaml(yamlContent)
  return params.length > 0
}

/**
 * Validate parameter values against definitions
 */
export function validateParameters(
  values: Record<string, any>,
  definitions: ParameterDefinition[]
): { valid: boolean; errors: Array<{ parameter: string; message: string }> } {
  const errors: Array<{ parameter: string; message: string }> = []

  definitions.forEach(def => {
    const value = values[def.name]

    if (def.input === 'hidden') {
      return
    }

    // Check required fields
    if (def.required && (value === undefined || value === null || value === '')) {
      errors.push({
        parameter: def.name,
        message: `${def.label} is required`
      })
      return
    }

    // Type-specific validation
    if (value !== undefined && value !== null && value !== '') {
      switch (def.type) {
        case 'number':
          if (isNaN(Number(value))) {
            errors.push({
              parameter: def.name,
              message: `${def.label} must be a number`
            })
          } else {
            const numValue = Number(value)
            if (def.min !== undefined && numValue < def.min) {
              errors.push({
                parameter: def.name,
                message: `${def.label} must be at least ${def.min}`
              })
            }
            if (def.max !== undefined && numValue > def.max) {
              errors.push({
                parameter: def.name,
                message: `${def.label} must be at most ${def.max}`
              })
            }
          }
          break

        case 'select':
        case 'scorecard_select':
        case 'score_select':
        case 'score_version_select':
          if (def.options && !def.options.find(opt => opt.value === value)) {
            errors.push({
              parameter: def.name,
              message: `${def.label} has an invalid value`
            })
          }
          break

        case 'date':
          if (typeof value !== 'string' || Number.isNaN(Date.parse(value))) {
            errors.push({
              parameter: def.name,
              message: `${def.label} must be a valid date`
            })
          }
          break

        case 'date_range': {
          const range = value as DateRangeValue
          const start = typeof range?.start === 'string' ? range.start : ''
          const end = typeof range?.end === 'string' ? range.end : ''

          if (def.required && (!start || !end)) {
            errors.push({
              parameter: def.name,
              message: `${def.label} requires both start and end dates`
            })
            break
          }

          if ((start && Number.isNaN(Date.parse(start))) || (end && Number.isNaN(Date.parse(end)))) {
            errors.push({
              parameter: def.name,
              message: `${def.label} must include valid start and end dates`
            })
            break
          }

          if (start && end && new Date(start) > new Date(end)) {
            errors.push({
              parameter: def.name,
              message: `${def.label} start date must be before or equal to end date`
            })
          }
          break
        }
      }
    }

    // Check dependencies
    if (def.depends_on) {
      const dependencyValue = values[def.depends_on]
      if (!dependencyValue && value) {
        const depDef = definitions.find(d => d.name === def.depends_on)
        errors.push({
          parameter: def.name,
          message: `${def.label} requires ${depDef?.label || def.depends_on} to be selected first`
        })
      }
    }
  })

  return {
    valid: errors.length === 0,
    errors
  }
}

/**
 * Get default values for parameters
 */
export function getDefaultValues(definitions: ParameterDefinition[]): Record<string, any> {
  const defaults: Record<string, any> = {}
  
  definitions.forEach(def => {
    if (def.default !== undefined) {
      defaults[def.name] = def.default
    } else {
      // Set sensible defaults based on type
      switch (def.type) {
        case 'boolean':
          defaults[def.name] = false
          break
        case 'text':
        case 'select':
        case 'scorecard_select':
        case 'score_select':
        case 'score_version_select':
          defaults[def.name] = ''
          break
        case 'number':
          defaults[def.name] = def.min || 0
          break
        case 'date':
          defaults[def.name] = ''
          break
        case 'date_range':
          defaults[def.name] = { start: '', end: '' }
          break
      }
    }
  })

  return defaults
}

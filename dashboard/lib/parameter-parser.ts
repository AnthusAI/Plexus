/**
 * Utilities for parsing parameter definitions from YAML
 */

import yaml from 'js-yaml'
import { ParameterConfig, ParameterDefinition } from '@/types/parameters'

/**
 * Extract parameter definitions from YAML content
 * Supports frontmatter format: parameters section before --- separator
 */
export function parseParametersFromYaml(yamlContent: string): ParameterDefinition[] {
  try {
    // Check for YAML frontmatter (parameters section before ---)
    if (yamlContent.includes('---')) {
      const parts = yamlContent.split('---')
      if (parts.length >= 2) {
        // First part is the frontmatter
        const frontmatter = parts[0].trim()
        if (frontmatter) {
          const config = yaml.load(frontmatter) as ParameterConfig
          return config?.parameters || []
        }
      }
    }
    
    // Fallback: try to parse the whole thing
    const config = yaml.load(yamlContent) as ParameterConfig
    return config?.parameters || []
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
      }
    }
  })

  return defaults
}




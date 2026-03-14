/**
 * Utilities for parsing parameter definitions from YAML
 */

import yaml from 'js-yaml'
import { ParameterConfig, ParameterDefinition } from '@/types/parameters'

type LegacyParameterConfig = ParameterConfig & {
  configurable_parameters?: ParameterDefinition[]
}

type TactusParamDefinition = {
  type?: string
  input?: 'text' | 'textarea' | 'hidden'
  required?: boolean
  default?: any
  description?: string
  label?: string
  options?: Array<string | { value: string; label?: string }>
  enum?: Array<string | { value: string; label?: string }>
  depends_on?: string
  placeholder?: string
  rows?: number
  min?: number
  max?: number
  value?: any
}

type ProcedureYamlConfig = LegacyParameterConfig & {
  params?: Record<string, TactusParamDefinition>
}

function humanizeLabel(name: string): string {
  return name
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function normalizeParameterType(type?: string): ParameterDefinition['type'] {
  switch (type) {
    case 'number':
      return 'number'
    case 'boolean':
      return 'boolean'
    case 'select':
      return 'select'
    case 'scorecard_select':
      return 'scorecard_select'
    case 'score_select':
      return 'score_select'
    case 'score_version_select':
      return 'score_version_select'
    case 'string':
    case 'array':
    case 'object':
    default:
      return 'text'
  }
}

function normalizeOptions(
  options?: Array<string | { value: string; label?: string }>
): ParameterDefinition['options'] {
  if (!Array.isArray(options) || options.length === 0) {
    return undefined
  }

  return options.map((option) => {
    if (typeof option === 'string') {
      return { value: option, label: option }
    }

    return {
      value: option.value,
      label: option.label || option.value,
    }
  })
}

function normalizeListParameters(parameters: ParameterDefinition[] | undefined): ParameterDefinition[] {
  if (!Array.isArray(parameters)) {
    return []
  }

  return parameters.map((parameter) => ({
    ...parameter,
    type: normalizeParameterType(parameter.type),
    label: parameter.label || humanizeLabel(parameter.name),
    input: parameter.input,
    rows: parameter.rows,
  }))
}

function parseTactusParams(params: Record<string, TactusParamDefinition> | undefined): ParameterDefinition[] {
  if (!params || typeof params !== 'object') {
    return []
  }

  return Object.entries(params).map(([name, definition]) => ({
    name,
    label: definition.label || humanizeLabel(name),
    type: normalizeParameterType(definition.type),
    input: definition.input,
    required: definition.required,
    default: definition.default,
    description: definition.description,
    options: normalizeOptions(definition.options || definition.enum),
    depends_on: definition.depends_on,
    placeholder: definition.placeholder,
    rows: definition.rows,
    min: definition.min,
    max: definition.max,
  }))
}

function parseYamlContent(content: string): ParameterDefinition[] {
  const config = yaml.load(content) as ProcedureYamlConfig | undefined
  if (!config || typeof config !== 'object') {
    return []
  }

  const tactusParameters = parseTactusParams(config.params)
  if (tactusParameters.length > 0) {
    return tactusParameters
  }

  const explicitParameters = normalizeListParameters(config.parameters)
  if (explicitParameters.length > 0) {
    return explicitParameters
  }

  return normalizeListParameters(config.configurable_parameters)
}

/**
 * Extract parameter definitions from YAML content
 * Supports frontmatter format: parameters section before --- separator
 */
export function parseParametersFromYaml(yamlContent: string): ParameterDefinition[] {
  try {
    if (yamlContent.includes('---')) {
      const parts = yamlContent.split('---')
      if (parts.length >= 2) {
        const frontmatter = parts[0].trim()
        if (frontmatter) {
          const frontmatterParameters = parseYamlContent(frontmatter)
          if (frontmatterParameters.length > 0) {
            return frontmatterParameters
          }
        }
      }
    }

    return parseYamlContent(yamlContent)
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
 * Inject parameter values into a procedure YAML definition.
 *
 * Tactus `params:` entries get their submitted values stored as both `value`
 * and `default` so the created run is self-contained.
 */
export function injectParameterValuesIntoYaml(
  yamlContent: string,
  values: Record<string, any>
): string {
  try {
    const config = yaml.load(yamlContent) as ProcedureYamlConfig | undefined
    if (!config || typeof config !== 'object') {
      return yamlContent
    }

    if (config.params && typeof config.params === 'object') {
      for (const [name, value] of Object.entries(values)) {
        if (!(name in config.params)) {
          continue
        }

        const definition = config.params[name]
        if (definition && typeof definition === 'object') {
          definition.value = value
          definition.default = value
        } else {
          config.params[name] = {
            type: typeof value === 'number' ? 'number' : typeof value === 'boolean' ? 'boolean' : 'string',
            default: value,
            value,
          }
        }
      }

      return yaml.dump(config, { lineWidth: -1 })
    }

    if (Array.isArray(config.parameters)) {
      config.parameters = config.parameters.map((parameter) => ({
        ...parameter,
        value: values[parameter.name] !== undefined ? values[parameter.name] : parameter.default,
      }))
      return yaml.dump(config, { lineWidth: -1 })
    }

    if (Array.isArray(config.configurable_parameters)) {
      config.configurable_parameters = config.configurable_parameters.map((parameter) => ({
        ...parameter,
        value: values[parameter.name] !== undefined ? values[parameter.name] : parameter.default,
      }))
      return yaml.dump(config, { lineWidth: -1 })
    }

    return yamlContent
  } catch (error) {
    console.error('Error injecting parameter values into YAML:', error)
    return yamlContent
  }
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

    if (def.required && (value === undefined || value === null || value === '')) {
      errors.push({
        parameter: def.name,
        message: `${def.label} is required`
      })
      return
    }

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

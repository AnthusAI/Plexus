/**
 * YAML DSL Linter - TypeScript Implementation
 * 
 * Provides comprehensive linting for YAML-based domain-specific languages,
 * including syntax validation and domain-specific rule checking.
 */

import * as yaml from 'js-yaml'

export interface LintMessage {
  // Message classification
  level: 'error' | 'warning' | 'info' | 'success'
  code: string // Unique error code (e.g., 'YAML_SYNTAX_001', 'DOMAIN_REQUIRED_FIELD')
  
  // Message content
  title: string
  message: string
  suggestion?: string
  
  // Location information
  line?: number
  column?: number
  
  // Documentation links
  doc_url?: string
  doc_section?: string
  
  // Additional context
  context?: Record<string, any>
}

export interface LintResult {
  // Overall status
  is_valid: boolean
  success_message?: string
  
  // Individual messages
  messages: LintMessage[]
  
  // Statistics
  error_count: number
  warning_count: number
  info_count: number
  
  // Parsed content (if successful)
  parsed_content?: Record<string, any>
}

export interface ValidationRule {
  rule_id: string
  description: string
  severity: 'error' | 'warning' | 'info'
  validate: (data: Record<string, any>) => LintMessage[]
}

export class YamlLinter {
  private schema?: Record<string, any>
  private rules: ValidationRule[]
  private docBaseUrl: string

  constructor(
    schema?: Record<string, any>,
    customRules: ValidationRule[] = [],
    docBaseUrl: string = 'https://docs.plexus.ai/yaml-dsl'
  ) {
    this.schema = schema
    this.rules = customRules
    this.docBaseUrl = docBaseUrl
  }

  /**
   * Lint a YAML document for syntax and domain-specific issues.
   */
  lint(yamlContent: string, sourcePath?: string): LintResult {
    const result: LintResult = {
      is_valid: true,
      messages: [],
      error_count: 0,
      warning_count: 0,
      info_count: 0
    }

    try {
      // Stage 1: YAML Syntax Validation
      const parsedContent = this.validateSyntax(yamlContent, result)
      
      if (!result.is_valid) {
        return result
      }

      result.parsed_content = parsedContent || undefined

      // Stage 2: Schema Validation (if schema provided)
      if (this.schema && parsedContent) {
        this.validateSchema(parsedContent, result)
      }

      // Stage 3: Domain-specific Rule Validation
      if (parsedContent) {
        this.validateRules(parsedContent, result)
      }

      // Stage 4: Generate success message if no issues
      if (result.is_valid && result.messages.length === 0) {
        result.success_message = "✅ No issues found – nice work! Your YAML is well-formed and follows all domain rules."
        this.addMessage(result, {
          level: 'success',
          code: 'VALIDATION_SUCCESS',
          title: 'Validation Successful',
          message: result.success_message,
          doc_url: `${this.docBaseUrl}/best-practices`
        })
      }

    } catch (error) {
      console.error('Unexpected error during linting:', error)
      this.addMessage(result, {
        level: 'error',
        code: 'LINTER_INTERNAL_ERROR',
        title: 'Internal Linter Error',
        message: `An unexpected error occurred during validation: ${error instanceof Error ? error.message : String(error)}`,
        suggestion: 'Please check your YAML syntax and try again. If the issue persists, please report this as a bug.',
        doc_url: `${this.docBaseUrl}/troubleshooting`
      })
    }

    return result
  }

  private validateSyntax(yamlContent: string, result: LintResult): Record<string, any> | null {
    try {
      // Parse the YAML content
      const parsed = yaml.load(yamlContent)

      // Handle empty documents
      if (parsed === null || parsed === undefined) {
        this.addMessage(result, {
          level: 'warning',
          code: 'YAML_EMPTY_DOCUMENT',
          title: 'Empty Document',
          message: 'The YAML document is empty or contains only comments.',
          suggestion: 'Consider adding some content or removing the file if not needed.',
          doc_url: `${this.docBaseUrl}/structure`
        })
        return {}
      }

      return parsed as Record<string, any>

         } catch (error: unknown) {
       if (error instanceof yaml.YAMLException) {
         this.addMessage(result, {
           level: 'error',
           code: 'YAML_SYNTAX_ERROR',
           title: 'YAML Syntax Error',
           message: error.message,
           suggestion: this.getSyntaxSuggestion(error),
           line: error.mark?.line ? error.mark.line + 1 : undefined, // js-yaml uses 0-based line numbers
           column: error.mark?.column ? error.mark.column + 1 : undefined,
           doc_url: `${this.docBaseUrl}/syntax-errors`
         })
       } else {
         this.addMessage(result, {
           level: 'error',
           code: 'YAML_GENERAL_ERROR',
           title: 'YAML Error',
           message: `YAML processing error: ${error instanceof Error ? error.message : String(error)}`,
           suggestion: 'Please check your YAML syntax and formatting.',
           doc_url: `${this.docBaseUrl}/syntax-errors`
         })
       }
       return null
     }
  }

  private validateSchema(parsedContent: Record<string, any>, result: LintResult): void {
    // Basic schema validation - in a real implementation, you might use a library like Ajv
    if (!this.schema) return

    try {
      // This is a simplified schema validation
      // In production, you'd want to use a proper JSON Schema validator like Ajv
      this.validateObject(parsedContent, this.schema, '', result)
    } catch (error) {
      this.addMessage(result, {
        level: 'error',
        code: 'SCHEMA_VALIDATION_INTERNAL_ERROR',
        title: 'Schema Validation Error',
        message: `An error occurred during schema validation: ${error instanceof Error ? error.message : String(error)}`,
        suggestion: 'Please check your schema and data, or report this as a bug.',
        doc_url: `${this.docBaseUrl}/troubleshooting`
      })
    }
  }

  private validateObject(data: any, schema: any, path: string, result: LintResult): void {
    // Simple schema validation implementation
    if (schema.type) {
      const expectedType = schema.type
      const actualType = Array.isArray(data) ? 'array' : typeof data
      
      if (actualType !== expectedType) {
        this.addMessage(result, {
          level: 'error',
          code: 'SCHEMA_TYPE_ERROR',
          title: 'Schema Type Error',
          message: `Field '${path}' should be ${expectedType}, but got ${actualType}.`,
          suggestion: `Please ensure '${path}' is a ${expectedType}.`,
          doc_url: `${this.docBaseUrl}/schema-validation`,
          context: { field_path: path, expected_type: expectedType, actual_type: actualType }
        })
        return
      }
    }

    if (schema.required && Array.isArray(schema.required)) {
      for (const requiredField of schema.required) {
        if (!(requiredField in data)) {
          this.addMessage(result, {
            level: 'error',
            code: 'SCHEMA_REQUIRED_FIELD',
            title: 'Required Field Missing',
            message: `Required field '${path}.${requiredField}' is missing.`,
            suggestion: `Please add the '${path}.${requiredField}' field to your configuration.`,
            doc_url: `${this.docBaseUrl}/required-fields`,
            context: { field_path: `${path}.${requiredField}` }
          })
        }
      }
    }

    if (schema.properties && typeof data === 'object' && data !== null) {
      for (const [key, value] of Object.entries(data)) {
        if (schema.properties[key]) {
          const subPath = path ? `${path}.${key}` : key
          this.validateObject(value, schema.properties[key], subPath, result)
        }
      }
    }
  }

  private validateRules(parsedContent: Record<string, any>, result: LintResult): void {
    for (const rule of this.rules) {
      try {
        const ruleMessages = rule.validate(parsedContent)
        for (const message of ruleMessages) {
          this.addMessage(result, message)
        }
      } catch (error) {
        this.addMessage(result, {
          level: 'error',
          code: 'RULE_ENGINE_ERROR',
          title: 'Rule Validation Error',
          message: `Error running rule '${rule.rule_id}': ${error instanceof Error ? error.message : String(error)}`,
          suggestion: 'Please check the rule configuration or report this as a bug.',
          context: { rule_id: rule.rule_id, error: String(error) }
        })
      }
    }
  }

  private addMessage(result: LintResult, message: LintMessage): void {
    result.messages.push(message)

    if (message.level === 'error') {
      result.error_count++
      result.is_valid = false
    } else if (message.level === 'warning') {
      result.warning_count++
    } else if (message.level === 'info') {
      result.info_count++
    }
  }

  private getSyntaxSuggestion(error: yaml.YAMLException): string {
    const message = error.message.toLowerCase()

    if (message.includes('tab')) {
      return "YAML doesn't allow tabs for indentation. Please use spaces instead."
    } else if (message.includes('indent')) {
      return "Check your indentation. YAML requires consistent spacing (usually 2 or 4 spaces per level)."
    } else if (message.includes('unexpected character') || message.includes('cannot start')) {
      return "This character cannot start a YAML value. Try quoting the value if it contains special characters."
    } else if (message.includes('mapping')) {
      return "Check that all mapping keys are properly formatted and indented."
    } else if (message.includes('sequence')) {
      return "Check that list items (starting with '-') are properly indented."
    } else if (message.includes('expected')) {
      return "The YAML structure is incomplete. Check for missing colons, brackets, or quotes."
    } else {
      return "Please check the YAML syntax around this location."
    }
  }
}

// Example validation rules

export class RequiredFieldRule implements ValidationRule {
  rule_id: string
  description: string
  severity: 'error' | 'warning' | 'info' = 'error'
  
  constructor(
    private fieldPath: string,
    ruleId?: string
  ) {
    this.rule_id = ruleId || `REQUIRED_FIELD_${fieldPath.toUpperCase().replace(/\./g, '_')}`
    this.description = `Field '${fieldPath}' is required`
  }

  validate(data: Record<string, any>): LintMessage[] {
    const messages: LintMessage[] = []
    
    // Navigate to the field using dot notation
    let current: any = data
    const pathParts = this.fieldPath.split('.')
    
    try {
      for (let i = 0; i < pathParts.length - 1; i++) {
        const part = pathParts[i]
        if (typeof current !== 'object' || current === null || !(part in current)) {
          throw new Error(`Path not found: ${part}`)
        }
        current = current[part]
      }
      
      // Check if the final field exists
      const finalField = pathParts[pathParts.length - 1]
      if (typeof current !== 'object' || current === null || !(finalField in current)) {
        messages.push({
          level: this.severity,
          code: this.rule_id,
          title: 'Required Field Missing',
          message: `Required field '${this.fieldPath}' is missing.`,
          suggestion: `Please add the '${this.fieldPath}' field to your configuration.`,
          doc_url: 'https://docs.plexus.ai/yaml-dsl/required-fields',
          context: { field_path: this.fieldPath }
        })
      } else if (current[finalField] === null || current[finalField] === '') {
        messages.push({
          level: this.severity,
          code: this.rule_id,
          title: 'Required Field Empty',
          message: `Required field '${this.fieldPath}' is empty.`,
          suggestion: `Please provide a value for the '${this.fieldPath}' field.`,
          doc_url: 'https://docs.plexus.ai/yaml-dsl/required-fields',
          context: { field_path: this.fieldPath }
        })
      }
      
    } catch (error) {
      messages.push({
        level: this.severity,
        code: this.rule_id,
        title: 'Required Field Missing',
        message: `Required field '${this.fieldPath}' is missing.`,
        suggestion: `Please add the '${this.fieldPath}' field to your configuration.`,
        doc_url: 'https://docs.plexus.ai/yaml-dsl/required-fields',
        context: { field_path: this.fieldPath }
      })
    }
    
    return messages
  }
}

export class AllowedValuesRule implements ValidationRule {
  rule_id: string
  description: string
  severity: 'error' | 'warning' | 'info' = 'error'
  
  constructor(
    private fieldPath: string,
    private allowedValues: any[],
    ruleId?: string
  ) {
    this.rule_id = ruleId || `ALLOWED_VALUES_${fieldPath.toUpperCase().replace(/\./g, '_')}`
    this.description = `Field '${fieldPath}' must be one of: ${allowedValues.join(', ')}`
  }

  validate(data: Record<string, any>): LintMessage[] {
    const messages: LintMessage[] = []
    
    // Navigate to the field
    let current: any = data
    const pathParts = this.fieldPath.split('.')
    
    try {
      for (const part of pathParts) {
        if (typeof current !== 'object' || current === null || !(part in current)) {
          // Field doesn't exist - not our concern
          return messages
        }
        current = current[part]
      }
      
      // Check if value is allowed
      if (!this.allowedValues.includes(current)) {
        messages.push({
          level: this.severity,
          code: this.rule_id,
          title: 'Invalid Field Value',
          message: `Field '${this.fieldPath}' has invalid value '${current}'.`,
          suggestion: `Please use one of the allowed values: ${this.allowedValues.join(', ')}`,
          doc_url: 'https://docs.plexus.ai/yaml-dsl/field-values',
          context: {
            field_path: this.fieldPath,
            current_value: current,
            allowed_values: this.allowedValues
          }
        })
      }
      
    } catch (error) {
      // Field path is invalid - not our concern
    }
    
    return messages
  }
}

export class TypeValidationRule implements ValidationRule {
  rule_id: string
  description: string
  severity: 'error' | 'warning' | 'info' = 'error'
  
  constructor(
    private fieldPath: string,
    private expectedType: 'string' | 'number' | 'boolean' | 'object' | 'array',
    ruleId?: string
  ) {
    this.rule_id = ruleId || `TYPE_VALIDATION_${fieldPath.toUpperCase().replace(/\./g, '_')}`
    this.description = `Field '${fieldPath}' must be of type ${expectedType}`
  }

  validate(data: Record<string, any>): LintMessage[] {
    const messages: LintMessage[] = []
    
    // Navigate to the field
    let current: any = data
    const pathParts = this.fieldPath.split('.')
    
    try {
      for (const part of pathParts) {
        if (typeof current !== 'object' || current === null || !(part in current)) {
          // Field doesn't exist - not our concern
          return messages
        }
        current = current[part]
      }
      
      // Check type
      const actualType = Array.isArray(current) ? 'array' : typeof current
      if (actualType !== this.expectedType) {
        messages.push({
          level: this.severity,
          code: this.rule_id,
          title: 'Invalid Field Type',
          message: `Field '${this.fieldPath}' should be ${this.expectedType}, but got ${actualType}.`,
          suggestion: `Please ensure '${this.fieldPath}' is a ${this.expectedType}.`,
          doc_url: 'https://docs.plexus.ai/yaml-dsl/data-types',
          context: {
            field_path: this.fieldPath,
            expected_type: this.expectedType,
            actual_type: actualType
          }
        })
      }
      
    } catch (error) {
      // Field path is invalid - not our concern
    }
    
    return messages
  }
}
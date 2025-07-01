/**
 * YAML DSL Schemas and Validation Rules
 * 
 * Defines the schemas and validation rules for different YAML formats used in the application.
 */

import { 
  YamlLinter, 
  RequiredFieldRule, 
  AllowedValuesRule, 
  TypeValidationRule,
  type ValidationRule 
} from './yaml-linter'

// Score Configuration Schema
export const SCORE_YAML_SCHEMA = {
  type: 'object',
  required: ['name', 'key'],
  properties: {
    name: {
      type: 'string',
      minLength: 1,
      description: 'Human-readable name for the score'
    },
    key: {
      type: 'string',
      pattern: '^[a-z0-9_-]+$',
      description: 'Unique identifier for the score (lowercase, alphanumeric, underscores, and hyphens only)'
    },
    externalId: {
      type: 'string',
      description: 'External ID for the score (camelCase format)'
    },
    external_id: {
      type: 'string',
      description: 'External ID for the score (snake_case format)'
    },
    description: {
      type: 'string',
      description: 'Detailed description of what this score measures'
    },
    type: {
      type: 'string',
      enum: ['binary', 'numeric', 'categorical', 'text'],
      description: 'Type of score output'
    },
    version: {
      type: 'string',
      description: 'Version identifier for the score'
    },
    tags: {
      type: 'array',
      items: { type: 'string' },
      description: 'Tags for categorizing the score'
    },
    config: {
      type: 'object',
      description: 'Score-specific configuration parameters'
    }
  },
  additionalProperties: true
}

// Data Source Configuration Schema
export const DATA_SOURCE_YAML_SCHEMA = {
  type: 'object',
  required: ['type'],
  properties: {
    type: {
      type: 'string',
      enum: ['file', 'database', 'api', 'stream'],
      description: 'Type of data source'
    },
    name: {
      type: 'string',
      description: 'Human-readable name for the data source'
    },
    connection: {
      type: 'object',
      properties: {
        host: { type: 'string' },
        port: { type: 'number' },
        database: { type: 'string' },
        username: { type: 'string' },
        password: { type: 'string' },
        ssl: { type: 'boolean' }
      },
      description: 'Connection parameters for the data source'
    },
    query: {
      type: 'string',
      description: 'Query or filter to apply to the data source'
    },
    format: {
      type: 'string',
      enum: ['csv', 'json', 'parquet', 'xlsx', 'sql'],
      description: 'Format of the data'
    },
    schema: {
      type: 'object',
      description: 'Schema definition for the data'
    },
    refresh: {
      type: 'object',
      properties: {
        enabled: { type: 'boolean' },
        interval: { type: 'string' },
        schedule: { type: 'string' }
      },
      description: 'Refresh settings for the data source'
    }
  },
  additionalProperties: true
}

// Score validation rules
export function createScoreValidationRules(): ValidationRule[] {
  return [
    // Required fields
    new RequiredFieldRule('name'),
    new RequiredFieldRule('key'),

    // Type validation
    new TypeValidationRule('name', 'string'),
    new TypeValidationRule('key', 'string'),
    new TypeValidationRule('description', 'string'),

    // Key format validation
    {
      rule_id: 'SCORE_KEY_FORMAT',
      description: 'Score key must be lowercase with only letters, numbers, underscores, and hyphens',
      severity: 'error',
      validate: (data: Record<string, any>) => {
        const messages = []
        if (data.key && typeof data.key === 'string') {
          const keyPattern = /^[a-z0-9_-]+$/
          if (!keyPattern.test(data.key)) {
            messages.push({
              level: 'error' as const,
              code: 'SCORE_KEY_FORMAT',
              title: 'Invalid Key Format',
              message: `Score key '${data.key}' contains invalid characters.`,
              suggestion: 'Use only lowercase letters, numbers, underscores, and hyphens. Example: "sentiment_analysis" or "quality-score"',
              doc_url: 'https://docs.plexus.ai/yaml-dsl/score-keys',
              context: { field_path: 'key', current_value: data.key }
            })
          }
        }
        return messages
      }
    },

    // External ID consistency check
    {
      rule_id: 'SCORE_EXTERNAL_ID_CONSISTENCY',
      description: 'External ID should use consistent format (either camelCase or snake_case, not both)',
      severity: 'warning',
      validate: (data: Record<string, any>) => {
        const messages = []
        const hasCamelCase = 'externalId' in data
        const hasSnakeCase = 'external_id' in data
        
        if (hasCamelCase && hasSnakeCase) {
          messages.push({
            level: 'warning' as const,
            code: 'SCORE_EXTERNAL_ID_CONSISTENCY',
            title: 'Inconsistent External ID Format',
            message: 'Both externalId and external_id are present. Use only one format.',
            suggestion: 'Choose either camelCase (externalId) or snake_case (external_id) and remove the other.',
            doc_url: 'https://docs.plexus.ai/yaml-dsl/external-ids',
            context: { has_camel_case: hasCamelCase, has_snake_case: hasSnakeCase }
          })
        }
        return messages
      }
    },

    // Type validation for common score types
    new AllowedValuesRule('type', ['binary', 'numeric', 'categorical', 'text'])
  ]
}

// Data source validation rules
export function createDataSourceValidationRules(): ValidationRule[] {
  return [
    // Required fields
    new RequiredFieldRule('type'),

    // Type validation
    new TypeValidationRule('type', 'string'),
    new TypeValidationRule('name', 'string'),

    // Allowed data source types
    new AllowedValuesRule('type', ['file', 'database', 'api', 'stream']),

    // Format validation
    new AllowedValuesRule('format', ['csv', 'json', 'parquet', 'xlsx', 'sql']),

    // Connection validation for database types
    {
      rule_id: 'DATA_SOURCE_DB_CONNECTION',
      description: 'Database data sources should have connection information',
      severity: 'warning',
      validate: (data: Record<string, any>) => {
        const messages = []
        if (data.type === 'database' && !data.connection) {
          messages.push({
            level: 'warning' as const,
            code: 'DATA_SOURCE_DB_CONNECTION',
            title: 'Missing Database Connection',
            message: 'Database data sources should include connection information.',
            suggestion: 'Add a "connection" section with host, port, database, and other connection parameters.',
            doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#database',
            context: { data_source_type: data.type }
          })
        }
        return messages
      }
    },

    // Query validation for database and API types
    {
      rule_id: 'DATA_SOURCE_QUERY_RECOMMENDATION',
      description: 'Database and API data sources benefit from having a query defined',
      severity: 'info',
      validate: (data: Record<string, any>) => {
        const messages = []
        if ((data.type === 'database' || data.type === 'api') && !data.query) {
          messages.push({
            level: 'info' as const,
            code: 'DATA_SOURCE_QUERY_RECOMMENDATION',
            title: 'Consider Adding Query',
            message: `${data.type === 'database' ? 'Database' : 'API'} data sources often benefit from having a query defined.`,
            suggestion: `Add a "query" field to specify the ${data.type === 'database' ? 'SQL query' : 'API endpoint or filter'} for this data source.`,
            doc_url: `https://docs.plexus.ai/yaml-dsl/data-sources#${data.type}`,
            context: { data_source_type: data.type }
          })
        }
        return messages
      }
    }
  ]
}

// Factory functions for creating linters
export function createScoreLinter(): YamlLinter {
  return new YamlLinter(
    SCORE_YAML_SCHEMA,
    createScoreValidationRules(),
    'https://docs.plexus.ai/yaml-dsl/scores'
  )
}

export function createDataSourceLinter(): YamlLinter {
  return new YamlLinter(
    DATA_SOURCE_YAML_SCHEMA,
    createDataSourceValidationRules(),
    'https://docs.plexus.ai/yaml-dsl/data-sources'
  )
}

// Utility function to determine linter type from context
export function createLinterForContext(context: 'score' | 'data-source'): YamlLinter {
  switch (context) {
    case 'score':
      return createScoreLinter()
    case 'data-source':
      return createDataSourceLinter()
    default:
      throw new Error(`Unknown linter context: ${context}`)
  }
}
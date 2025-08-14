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
  required: ['class'],
  properties: {
    class: {
      type: 'string',
      enum: ['CallCriteriaDBCache', 'FeedbackItems'],
      description: 'Data source class - CallCriteriaDBCache or FeedbackItems'
    },
    queries: {
      type: 'array',
      items: {
        type: 'object',
        required: ['scorecard_id', 'number'],
        properties: {
          scorecard_id: {
            type: 'number',
            description: 'ID of the scorecard to query'
          },
          number: {
            type: 'number',
            minimum: 1,
            description: 'Number of records to retrieve'
          },
          query: {
            type: 'string',
            description: 'Custom SQL query with placeholders like {scorecard_id} and {number}'
          },
          minimum_calibration_count: {
            type: 'number',
            minimum: 0,
            description: 'Minimum calibration count required'
          }
        },
        additionalProperties: false
      },
      description: 'List of database queries to execute'
    },
    searches: {
      type: 'array',
      items: {
        type: 'object',
        required: ['item_list_filename'],
        properties: {
          item_list_filename: {
            type: 'string',
            pattern: '^.+\\.(csv|txt)$',
            description: 'Path to CSV or text file containing search items'
          }
        },
        additionalProperties: false
      },
      description: 'List of file-based searches to perform'
    },
    balance: {
      type: 'boolean',
      description: 'Whether to balance the dataset (defaults to true)'
    },
    // FeedbackItems specific fields
    scorecard: {
      oneOf: [
        { type: 'string' },
        { type: 'number' }
      ],
      description: 'Scorecard identifier (name, key, ID, or external ID)'
    },
    score: {
      oneOf: [
        { type: 'string' },
        { type: 'number' }
      ],
      description: 'Score identifier (name, key, ID, or external ID)'
    },
    days: {
      type: 'number',
      minimum: 1,
      description: 'Number of days back to search for feedback items'
    },
    limit: {
      type: 'number',
      minimum: 1,
      description: 'Maximum total number of items in the dataset'
    },
    limit_per_cell: {
      type: 'number',
      minimum: 1,
      description: 'Maximum number of items to sample from each confusion matrix cell'
    }
  },
  additionalProperties: false,
  anyOf: [
    { 
      // CallCriteriaDBCache requirements
      properties: { class: { const: 'CallCriteriaDBCache' } },
      anyOf: [
        { required: ['queries'] },
        { required: ['searches'] }
      ]
    },
    {
      // FeedbackItems requirements
      properties: { class: { const: 'FeedbackItems' } },
      required: ['scorecard', 'score', 'days']
    }
  ]
}

// Score validation rules
export function createScoreValidationRules(): ValidationRule[] {
  return [
    // Required fields
    new RequiredFieldRule('name'),
    new RequiredFieldRule('class'),

    // Type validation
    new TypeValidationRule('name', 'string'),
    new TypeValidationRule('class', 'string'),
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
    new RequiredFieldRule('class'),

    // Type validation
    new TypeValidationRule('class', 'string'),

    // Allowed data source classes
    new AllowedValuesRule('class', ['CallCriteriaDBCache', 'FeedbackItems']),

    // Ensure either queries or searches is present (only for CallCriteriaDBCache)
    {
      rule_id: 'DATA_SOURCE_QUERIES_OR_SEARCHES_REQUIRED',
      description: 'CallCriteriaDBCache data source must have either queries or searches defined',
      severity: 'error',
      validate: (data: Record<string, any>) => {
        const messages: any[] = []
        
        // Only apply this rule to CallCriteriaDBCache
        if (data.class !== 'CallCriteriaDBCache') {
          return messages
        }
        
        const hasQueries = data.queries && Array.isArray(data.queries) && data.queries.length > 0
        const hasSearches = data.searches && Array.isArray(data.searches) && data.searches.length > 0
        
        if (!hasQueries && !hasSearches) {
          messages.push({
            level: 'error' as const,
            code: 'DATA_SOURCE_QUERIES_OR_SEARCHES_REQUIRED',
            title: 'Missing Queries or Searches',
            message: 'Data source must have either "queries" or "searches" defined (or both).',
            suggestion: 'Add a "queries" section for database queries or a "searches" section for file-based searches.',
            doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#structure',
            context: { has_queries: hasQueries, has_searches: hasSearches }
          })
        }
        return messages
      }
    },

    // Validate query structure
    {
      rule_id: 'DATA_SOURCE_QUERY_STRUCTURE',
      description: 'Query items must have required fields and valid structure',
      severity: 'error',
      validate: (data: Record<string, any>) => {
        const messages: any[] = []
        
        if (data.queries && Array.isArray(data.queries)) {
          data.queries.forEach((query: any, index: number) => {
            const queryPath = `queries[${index}]`
            
            // Check required fields
            if (!query.scorecard_id) {
              messages.push({
                level: 'error' as const,
                code: 'DATA_SOURCE_QUERY_MISSING_SCORECARD_ID',
                title: 'Missing Scorecard ID',
                message: `Query item ${index + 1} is missing required "scorecard_id" field.`,
                suggestion: 'Add a "scorecard_id" field with a numeric scorecard identifier.',
                doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#queries',
                context: { query_index: index, field: 'scorecard_id' }
              })
            }
            
            if (!query.number) {
              messages.push({
                level: 'error' as const,
                code: 'DATA_SOURCE_QUERY_MISSING_NUMBER',
                title: 'Missing Number Field',
                message: `Query item ${index + 1} is missing required "number" field.`,
                suggestion: 'Add a "number" field specifying how many records to retrieve.',
                doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#queries',
                context: { query_index: index, field: 'number' }
              })
            }
            
            // Validate number is positive
            if (query.number && (typeof query.number !== 'number' || query.number < 1)) {
              messages.push({
                level: 'error' as const,
                code: 'DATA_SOURCE_QUERY_INVALID_NUMBER',
                title: 'Invalid Number Value',
                message: `Query item ${index + 1} has invalid "number" value. Must be a positive integer.`,
                suggestion: 'Set "number" to a positive integer (e.g., 1000, 5000).',
                doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#queries',
                context: { query_index: index, current_value: query.number }
              })
            }
            
            // Validate scorecard_id is numeric
            if (query.scorecard_id && typeof query.scorecard_id !== 'number') {
              messages.push({
                level: 'error' as const,
                code: 'DATA_SOURCE_QUERY_INVALID_SCORECARD_ID',
                title: 'Invalid Scorecard ID',
                message: `Query item ${index + 1} has invalid "scorecard_id" value. Must be a number.`,
                suggestion: 'Set "scorecard_id" to a numeric scorecard identifier (e.g., 1329, 555).',
                doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#queries',
                context: { query_index: index, current_value: query.scorecard_id }
              })
            }
          })
        }
        
        return messages
      }
    },

    // Validate searches structure
    {
      rule_id: 'DATA_SOURCE_SEARCH_STRUCTURE',
      description: 'Search items must have required fields and valid file paths',
      severity: 'error',
      validate: (data: Record<string, any>) => {
        const messages: any[] = []
        
        if (data.searches && Array.isArray(data.searches)) {
          data.searches.forEach((search: any, index: number) => {
            // Check required fields
            if (!search.item_list_filename) {
              messages.push({
                level: 'error' as const,
                code: 'DATA_SOURCE_SEARCH_MISSING_FILENAME',
                title: 'Missing Item List Filename',
                message: `Search item ${index + 1} is missing required "item_list_filename" field.`,
                suggestion: 'Add an "item_list_filename" field with a path to a CSV or text file.',
                doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#searches',
                context: { search_index: index, field: 'item_list_filename' }
              })
            }
            
            // Validate file extension
            if (search.item_list_filename && typeof search.item_list_filename === 'string') {
              const filename = search.item_list_filename.toLowerCase()
              if (!filename.endsWith('.csv') && !filename.endsWith('.txt')) {
                messages.push({
                  level: 'warning' as const,
                  code: 'DATA_SOURCE_SEARCH_INVALID_FILE_TYPE',
                  title: 'Unusual File Type',
                  message: `Search item ${index + 1} file "${search.item_list_filename}" should typically be a .csv or .txt file.`,
                  suggestion: 'Use a .csv or .txt file for item lists.',
                  doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#searches',
                  context: { search_index: index, filename: search.item_list_filename }
                })
              }
            }
          })
        }
        
        return messages
      }
    },

    // FeedbackItems validation rules
    {
      rule_id: 'FEEDBACK_ITEMS_VALIDATION',
      description: 'FeedbackItems data source must have required parameters',
      severity: 'error',
      validate: (data: Record<string, any>) => {
        const messages: any[] = []
        
        // Only apply this rule to FeedbackItems
        if (data.class !== 'FeedbackItems') {
          return messages
        }
        
        // Required fields for FeedbackItems
        const requiredFields = ['scorecard', 'score', 'days']
        
        for (const field of requiredFields) {
          if (!(field in data) || data[field] === null || data[field] === '') {
            messages.push({
              level: 'error' as const,
              code: `FEEDBACK_ITEMS_MISSING_${field.toUpperCase()}`,
              title: `Missing ${field.charAt(0).toUpperCase() + field.slice(1)} Field`,
              message: `FeedbackItems data source is missing required "${field}" field.`,
              suggestion: `Add a "${field}" field to specify the ${field} parameter.`,
              doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
              context: { field }
            })
          }
        }
        
        // Validate days is positive integer
        if ('days' in data) {
          const days = data.days
          if (typeof days !== 'number' || days <= 0 || !Number.isInteger(days)) {
            messages.push({
              level: 'error' as const,
              code: 'FEEDBACK_ITEMS_INVALID_DAYS',
              title: 'Invalid Days Value',
              message: 'FeedbackItems "days" must be a positive integer.',
              suggestion: 'Set "days" to a positive integer (e.g., 7, 14, 30).',
              doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
              context: { current_value: days }
            })
          }
        }
        
        // Validate limit is positive integer if present
        if ('limit' in data) {
          const limit = data.limit
          if (typeof limit !== 'number' || limit <= 0 || !Number.isInteger(limit)) {
            messages.push({
              level: 'error' as const,
              code: 'FEEDBACK_ITEMS_INVALID_LIMIT',
              title: 'Invalid Limit Value',
              message: 'FeedbackItems "limit" must be a positive integer.',
              suggestion: 'Set "limit" to a positive integer (e.g., 100, 500, 1000).',
              doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
              context: { current_value: limit }
            })
          }
        }
        
        // Validate limit_per_cell is positive integer if present
        if ('limit_per_cell' in data) {
          const limitPerCell = data.limit_per_cell
          if (typeof limitPerCell !== 'number' || limitPerCell <= 0 || !Number.isInteger(limitPerCell)) {
            messages.push({
              level: 'error' as const,
              code: 'FEEDBACK_ITEMS_INVALID_LIMIT_PER_CELL',
              title: 'Invalid Limit Per Cell Value',
              message: 'FeedbackItems "limit_per_cell" must be a positive integer.',
              suggestion: 'Set "limit_per_cell" to a positive integer (e.g., 10, 50, 100).',
              doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
              context: { current_value: limitPerCell }
            })
          }
        }
        
        // Validate scorecard and score are strings or numbers
        for (const field of ['scorecard', 'score']) {
          if (field in data) {
            const value = data[field]
            if (typeof value !== 'string' && typeof value !== 'number') {
              messages.push({
                level: 'error' as const,
                code: `FEEDBACK_ITEMS_INVALID_${field.toUpperCase()}`,
                title: `Invalid ${field.charAt(0).toUpperCase() + field.slice(1)} Value`,
                message: `FeedbackItems "${field}" must be a string or number.`,
                suggestion: `Set "${field}" to a string name, key, or numeric ID.`,
                doc_url: 'https://docs.plexus.ai/yaml-dsl/data-sources#feedback-items',
                context: { field, current_value: value }
              })
            }
          }
        }
        
        return messages
      }
    },

    // Validate balance field
    new TypeValidationRule('balance', 'boolean')
  ]
}

// Experiment Configuration Schema
export const EXPERIMENT_YAML_SCHEMA = {
  type: 'object',
  required: ['name', 'class', 'value_function', 'exploration', 'budget', 'dataset'],
  properties: {
    name: {
      type: 'string',
      minLength: 1,
      description: 'Human-readable name for the experiment'
    },
    description: {
      type: 'string',
      description: 'Detailed description of what this experiment tests'
    },
    class: {
      type: 'object',
      required: ['field', 'values'],
      properties: {
        field: {
          type: 'string',
          description: 'The field name to classify'
        },
        values: {
          type: 'array',
          items: { type: 'string' },
          minItems: 2,
          description: 'Possible classification values'
        }
      },
      description: 'Classification configuration'
    },
    value_function: {
      type: 'object',
      required: ['type'],
      properties: {
        type: {
          type: 'string',
          enum: ['f1_macro', 'f1_micro', 'accuracy', 'precision', 'recall', 'roc_auc'],
          description: 'Type of value function to optimize'
        },
        weight: {
          type: 'number',
          minimum: 0,
          maximum: 1,
          description: 'Weight for this value function (0-1)'
        }
      },
      description: 'How we measure success'
    },
    exploration: {
      type: 'object',
      required: ['method'],
      properties: {
        method: {
          type: 'string',
          enum: ['beam_search', 'random_search', 'grid_search', 'genetic'],
          description: 'Exploration method to use'
        },
        beam_width: {
          type: 'number',
          minimum: 1,
          description: 'Beam width for beam search'
        },
        max_depth: {
          type: 'number',
          minimum: 1,
          description: 'Maximum depth for exploration'
        },
        population_size: {
          type: 'number',
          minimum: 1,
          description: 'Population size for genetic algorithms'
        }
      },
      description: 'Exploration method configuration'
    },
    budget: {
      type: 'object',
      properties: {
        max_versions: {
          type: 'number',
          minimum: 1,
          description: 'Maximum number of versions to try'
        },
        max_cost_usd: {
          type: 'number',
          minimum: 0,
          description: 'Maximum cost in USD'
        },
        timeout_minutes: {
          type: 'number',
          minimum: 1,
          description: 'Timeout in minutes'
        }
      },
      description: 'Budget constraints'
    },
    dataset: {
      type: 'object',
      required: ['source'],
      properties: {
        source: {
          type: 'string',
          enum: ['items', 'feedback', 'evaluations'],
          description: 'Source of the dataset'
        },
        filters: {
          type: 'object',
          description: 'Filters to apply to the dataset'
        },
        sample_size: {
          type: 'number',
          minimum: 1,
          description: 'Number of samples to use'
        }
      },
      description: 'Dataset configuration'
    }
  },
  additionalProperties: true
}

// Experiment validation rules
export function createExperimentValidationRules(): ValidationRule[] {
  return [
    // Required fields
    new RequiredFieldRule('name'),
    new RequiredFieldRule('class'),
    new RequiredFieldRule('value_function'),
    new RequiredFieldRule('exploration'),
    new RequiredFieldRule('budget'),
    new RequiredFieldRule('dataset'),

    // Type validation
    new TypeValidationRule('name', 'string'),
    new TypeValidationRule('description', 'string'),

    // Class validation
    {
      rule_id: 'EXPERIMENT_CLASS_STRUCTURE',
      description: 'Class configuration must have field and values',
      severity: 'error',
      validate: (data: Record<string, any>) => {
        const messages = []
        if (data.class && typeof data.class === 'object') {
          if (!data.class.field) {
            messages.push({
              level: 'error' as const,
              code: 'EXPERIMENT_CLASS_MISSING_FIELD',
              title: 'Missing Class Field',
              message: 'Class configuration is missing required "field" property.',
              suggestion: 'Add a "field" property specifying the classification field name.',
              doc_url: 'https://docs.plexus.ai/yaml-dsl/experiments#class',
              context: { field_path: 'class.field' }
            })
          }
          if (!data.class.values || !Array.isArray(data.class.values) || data.class.values.length < 2) {
            messages.push({
              level: 'error' as const,
              code: 'EXPERIMENT_CLASS_INVALID_VALUES',
              title: 'Invalid Class Values',
              message: 'Class configuration must have at least 2 values in the "values" array.',
              suggestion: 'Add a "values" array with at least 2 classification options (e.g., ["positive", "negative"]).',
              doc_url: 'https://docs.plexus.ai/yaml-dsl/experiments#class',
              context: { field_path: 'class.values', current_length: data.class.values?.length || 0 }
            })
          }
        }
        return messages
      }
    },

    // Value function validation
    {
      rule_id: 'EXPERIMENT_VALUE_FUNCTION_STRUCTURE',
      description: 'Value function must have valid type',
      severity: 'error',
      validate: (data: Record<string, any>) => {
        const messages = []
        if (data.value_function && typeof data.value_function === 'object') {
          const validTypes = ['f1_macro', 'f1_micro', 'accuracy', 'precision', 'recall', 'roc_auc']
          if (!data.value_function.type || !validTypes.includes(data.value_function.type)) {
            messages.push({
              level: 'error' as const,
              code: 'EXPERIMENT_VALUE_FUNCTION_INVALID_TYPE',
              title: 'Invalid Value Function Type',
              message: `Value function type must be one of: ${validTypes.join(', ')}.`,
              suggestion: `Set "type" to one of the supported values: ${validTypes.join(', ')}.`,
              doc_url: 'https://docs.plexus.ai/yaml-dsl/experiments#value-function',
              context: { field_path: 'value_function.type', valid_types: validTypes, current_value: data.value_function.type }
            })
          }
        }
        return messages
      }
    },

    // Exploration method validation
    {
      rule_id: 'EXPERIMENT_EXPLORATION_STRUCTURE',
      description: 'Exploration configuration must have valid method',
      severity: 'error',
      validate: (data: Record<string, any>) => {
        const messages = []
        if (data.exploration && typeof data.exploration === 'object') {
          const validMethods = ['beam_search', 'random_search', 'grid_search', 'genetic']
          if (!data.exploration.method || !validMethods.includes(data.exploration.method)) {
            messages.push({
              level: 'error' as const,
              code: 'EXPERIMENT_EXPLORATION_INVALID_METHOD',
              title: 'Invalid Exploration Method',
              message: `Exploration method must be one of: ${validMethods.join(', ')}.`,
              suggestion: `Set "method" to one of the supported values: ${validMethods.join(', ')}.`,
              doc_url: 'https://docs.plexus.ai/yaml-dsl/experiments#exploration',
              context: { field_path: 'exploration.method', valid_methods: validMethods, current_value: data.exploration.method }
            })
          }
        }
        return messages
      }
    },

    // Dataset validation
    {
      rule_id: 'EXPERIMENT_DATASET_STRUCTURE',
      description: 'Dataset configuration must have valid source',
      severity: 'error',
      validate: (data: Record<string, any>) => {
        const messages = []
        if (data.dataset && typeof data.dataset === 'object') {
          const validSources = ['items', 'feedback', 'evaluations']
          if (!data.dataset.source || !validSources.includes(data.dataset.source)) {
            messages.push({
              level: 'error' as const,
              code: 'EXPERIMENT_DATASET_INVALID_SOURCE',
              title: 'Invalid Dataset Source',
              message: `Dataset source must be one of: ${validSources.join(', ')}.`,
              suggestion: `Set "source" to one of the supported values: ${validSources.join(', ')}.`,
              doc_url: 'https://docs.plexus.ai/yaml-dsl/experiments#dataset',
              context: { field_path: 'dataset.source', valid_sources: validSources, current_value: data.dataset.source }
            })
          }
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

export function createExperimentLinter(): YamlLinter {
  return new YamlLinter(
    EXPERIMENT_YAML_SCHEMA,
    createExperimentValidationRules(),
    'https://docs.plexus.ai/yaml-dsl/experiments'
  )
}

// Utility function to determine linter type from context
export function createLinterForContext(context: 'score' | 'data-source' | 'experiment'): YamlLinter {
  switch (context) {
    case 'score':
      return createScoreLinter()
    case 'data-source':
      return createDataSourceLinter()
    case 'experiment':
      return createExperimentLinter()
    default:
      throw new Error(`Unknown linter context: ${context}`)
  }
}
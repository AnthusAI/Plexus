import { describe, it, expect } from '@jest/globals'
import { 
  parseParametersFromYaml, 
  hasParameters, 
  validateParameters, 
  getDefaultValues 
} from '../parameter-parser'
import { ParameterDefinition } from '@/types/parameters'

describe('parameter-parser', () => {
  describe('parseParametersFromYaml', () => {
    it('should parse basic parameter definitions', () => {
      const yaml = `
parameters:
  - name: test_param
    label: Test Parameter
    type: text
    required: true
`
      const result = parseParametersFromYaml(yaml)
      expect(result).toHaveLength(1)
      expect(result[0].name).toBe('test_param')
      expect(result[0].label).toBe('Test Parameter')
      expect(result[0].type).toBe('text')
      expect(result[0].required).toBe(true)
    })

    it('should parse multiple parameters', () => {
      const yaml = `
parameters:
  - name: param1
    label: Parameter 1
    type: text
  - name: param2
    label: Parameter 2
    type: number
    min: 0
    max: 100
`
      const result = parseParametersFromYaml(yaml)
      expect(result).toHaveLength(2)
      expect(result[1].min).toBe(0)
      expect(result[1].max).toBe(100)
    })

    it('should handle YAML without parameters', () => {
      const yaml = `
some_other_config:
  value: test
`
      const result = parseParametersFromYaml(yaml)
      expect(result).toHaveLength(0)
    })

    it('should handle invalid YAML', () => {
      const yaml = 'invalid: yaml: content:'
      const result = parseParametersFromYaml(yaml)
      expect(result).toHaveLength(0)
    })

    it('should parse parameter with options', () => {
      const yaml = `
parameters:
  - name: choice
    label: Choose One
    type: select
    options:
      - value: opt1
        label: Option 1
      - value: opt2
        label: Option 2
`
      const result = parseParametersFromYaml(yaml)
      expect(result[0].options).toHaveLength(2)
      expect(result[0].options![0].value).toBe('opt1')
    })

    it('should parse dependent parameters', () => {
      const yaml = `
parameters:
  - name: scorecard_id
    label: Scorecard
    type: scorecard_select
  - name: score_id
    label: Score
    type: score_select
    depends_on: scorecard_id
`
      const result = parseParametersFromYaml(yaml)
      expect(result[1].depends_on).toBe('scorecard_id')
    })

    it('should parse parameters from markdown report template header', () => {
      const yaml = `
parameters:
  - name: window
    label: Analysis Window
    type: date_range
    required: true

---

# Sample Report

\`\`\`block name="Feedback Analysis"
class: FeedbackAnalysis
scorecard: 1481
start_date: {{ window_start }}
end_date: {{ window_end }}
\`\`\`
`
      const result = parseParametersFromYaml(yaml)
      expect(result).toHaveLength(1)
      expect(result[0].name).toBe('window')
      expect(result[0].type).toBe('date_range')
    })

    it('should parse Tactus params mapping format', () => {
      const yaml = `
params:
  brief:
    type: string
    input: textarea
    rows: 8
    required: true
    description: Unstructured stakeholder brief
  account_identifier:
    type: string
    input: hidden
  dry_run:
    type: boolean
    default: false
`
      const result = parseParametersFromYaml(yaml)
      expect(result).toHaveLength(3)
      expect(result[0].name).toBe('brief')
      expect(result[0].type).toBe('text')
      expect(result[0].input).toBe('textarea')
      expect(result[0].rows).toBe(8)
      expect(result[0].required).toBe(true)
      expect(result[0].label).toBe('Brief')
      expect(result[1].name).toBe('account_identifier')
      expect(result[1].input).toBe('hidden')
      expect(result[2].name).toBe('dry_run')
      expect(result[2].type).toBe('boolean')
      expect(result[2].default).toBe(false)
    })

    it('should normalize date_range type in params mapping format', () => {
      const yaml = `
params:
  window:
    type: date_range
    required: true
`
      const result = parseParametersFromYaml(yaml)
      expect(result).toHaveLength(1)
      expect(result[0].name).toBe('window')
      expect(result[0].type).toBe('date_range')
      expect(result[0].required).toBe(true)
    })
  })

  describe('hasParameters', () => {
    it('should return true when parameters exist', () => {
      const yaml = `
parameters:
  - name: test
    label: Test
    type: text
`
      expect(hasParameters(yaml)).toBe(true)
    })

    it('should return false when no parameters exist', () => {
      const yaml = 'other_config: value'
      expect(hasParameters(yaml)).toBe(false)
    })
  })

  describe('validateParameters', () => {
    it('should validate required fields', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'required_field', label: 'Required', type: 'text', required: true }
      ]
      
      const result1 = validateParameters({}, definitions)
      expect(result1.valid).toBe(false)
      expect(result1.errors).toHaveLength(1)
      
      const result2 = validateParameters({ required_field: 'value' }, definitions)
      expect(result2.valid).toBe(true)
      expect(result2.errors).toHaveLength(0)
    })

    it('should validate number types', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'number_field', label: 'Number', type: 'number', required: true }
      ]
      
      const result1 = validateParameters({ number_field: 'not a number' }, definitions)
      expect(result1.valid).toBe(false)
      
      const result2 = validateParameters({ number_field: 42 }, definitions)
      expect(result2.valid).toBe(true)
    })

    it('should validate number min/max', () => {
      const definitions: ParameterDefinition[] = [
        { 
          name: 'age', 
          label: 'Age', 
          type: 'number', 
          required: true,
          min: 18,
          max: 65
        }
      ]
      
      const result1 = validateParameters({ age: 10 }, definitions)
      expect(result1.valid).toBe(false)
      expect(result1.errors[0].message).toContain('at least 18')
      
      const result2 = validateParameters({ age: 100 }, definitions)
      expect(result2.valid).toBe(false)
      expect(result2.errors[0].message).toContain('at most 65')
      
      const result3 = validateParameters({ age: 30 }, definitions)
      expect(result3.valid).toBe(true)
    })

    it('should validate dependencies', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'parent', label: 'Parent', type: 'select' },
        { name: 'child', label: 'Child', type: 'select', depends_on: 'parent' }
      ]
      
      const result1 = validateParameters({ child: 'value' }, definitions)
      expect(result1.valid).toBe(false)
      expect(result1.errors[0].message).toContain('Parent')
      
      const result2 = validateParameters({ parent: 'p1', child: 'c1' }, definitions)
      expect(result2.valid).toBe(true)
    })

    it('should allow optional fields to be empty', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'optional', label: 'Optional', type: 'text', required: false }
      ]
      
      const result = validateParameters({}, definitions)
      expect(result.valid).toBe(true)
    })

    it('should ignore required hidden fields during UI validation', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'account_identifier', label: 'Account Identifier', type: 'text', input: 'hidden', required: true },
        { name: 'brief', label: 'Brief', type: 'text', required: true }
      ]

      const result = validateParameters({ brief: 'hello' }, definitions)
      expect(result.valid).toBe(true)
    })

    it('should validate date_range completeness and ordering', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'window', label: 'Window', type: 'date_range', required: true }
      ]

      const missingEnd = validateParameters(
        { window: { start: '2026-01-01', end: '' } },
        definitions
      )
      expect(missingEnd.valid).toBe(false)

      const outOfOrder = validateParameters(
        { window: { start: '2026-02-01', end: '2026-01-01' } },
        definitions
      )
      expect(outOfOrder.valid).toBe(false)
      expect(outOfOrder.errors[0].message).toContain('before or equal')

      const validRange = validateParameters(
        { window: { start: '2026-01-01', end: '2026-02-01' } },
        definitions
      )
      expect(validRange.valid).toBe(true)
    })
  })

  describe('getDefaultValues', () => {
    it('should use defined defaults', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'field1', label: 'Field 1', type: 'text', default: 'default value' },
        { name: 'field2', label: 'Field 2', type: 'number', default: 42 }
      ]
      
      const result = getDefaultValues(definitions)
      expect(result.field1).toBe('default value')
      expect(result.field2).toBe(42)
    })

    it('should provide sensible defaults for types', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'text_field', label: 'Text', type: 'text' },
        { name: 'number_field', label: 'Number', type: 'number' },
        { name: 'bool_field', label: 'Boolean', type: 'boolean' }
      ]
      
      const result = getDefaultValues(definitions)
      expect(result.text_field).toBe('')
      expect(result.number_field).toBe(0)
      expect(result.bool_field).toBe(false)
    })

    it('should use min value for numbers when specified', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'age', label: 'Age', type: 'number', min: 18 }
      ]
      
      const result = getDefaultValues(definitions)
      expect(result.age).toBe(18)
    })

    it('should provide empty start/end for date_range defaults', () => {
      const definitions: ParameterDefinition[] = [
        { name: 'window', label: 'Window', type: 'date_range' }
      ]

      const result = getDefaultValues(definitions)
      expect(result.window).toEqual({ start: '', end: '' })
    })
  })
})

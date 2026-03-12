import yaml from 'yaml'

/**
 * Helper function to inject parameter values into YAML template
 * This is the same logic used in procedures-dashboard.tsx
 */
function injectParameterValues(templateYaml: string, parameters: Record<string, any>): string {
  try {
    const parsed = yaml.parse(templateYaml)
    
    // If there's a parameters section, add values to it
    if (parsed.parameters && Array.isArray(parsed.parameters)) {
      parsed.parameters = parsed.parameters.map((param: any) => ({
        ...param,
        value: parameters[param.name] // Add the actual value
      }))
    }
    
    // Convert back to YAML
    return yaml.stringify(parsed)
  } catch (error) {
    console.warn('Could not parse template YAML, using original:', error)
    return templateYaml
  }
}

describe('YAML Parameter Value Injection', () => {
  describe('injectParameterValues', () => {
    it('should inject values into parameter definitions', () => {
      const templateYaml = `
parameters:
  - name: scorecard_id
    label: Scorecard
    type: scorecard_select
    required: true
  - name: score_id
    label: Score
    type: score_select
    required: true
    depends_on: scorecard_id

class: BeamSearch
value: |
  return score - penalty
`

      const parameters = {
        scorecard_id: 'scorecard-123',
        score_id: 'score-456'
      }

      const result = injectParameterValues(templateYaml, parameters)
      const parsed = yaml.parse(result)

      expect(parsed.parameters).toHaveLength(2)
      expect(parsed.parameters[0].name).toBe('scorecard_id')
      expect(parsed.parameters[0].value).toBe('scorecard-123')
      expect(parsed.parameters[1].name).toBe('score_id')
      expect(parsed.parameters[1].value).toBe('score-456')
    })

    it('should preserve all original parameter properties', () => {
      const templateYaml = `
parameters:
  - name: test_param
    label: Test Parameter
    type: text
    required: true
    description: A test parameter
    placeholder: Enter value
    default: default_value
`

      const parameters = {
        test_param: 'injected_value'
      }

      const result = injectParameterValues(templateYaml, parameters)
      const parsed = yaml.parse(result)

      expect(parsed.parameters[0]).toEqual({
        name: 'test_param',
        label: 'Test Parameter',
        type: 'text',
        required: true,
        description: 'A test parameter',
        placeholder: 'Enter value',
        default: 'default_value',
        value: 'injected_value'
      })
    })

    it('should handle YAML without parameters section', () => {
      const templateYaml = `
class: BeamSearch
value: |
  return score - penalty
exploration: |
  You are a hypothesis engine
`

      const parameters = {
        scorecard_id: 'scorecard-123'
      }

      const result = injectParameterValues(templateYaml, parameters)
      const parsed = yaml.parse(result)

      expect(parsed.class).toBe('BeamSearch')
      expect(parsed.parameters).toBeUndefined()
    })

    it('should handle empty parameters object', () => {
      const templateYaml = `
parameters:
  - name: scorecard_id
    label: Scorecard
    type: scorecard_select
    required: true
`

      const parameters = {}

      const result = injectParameterValues(templateYaml, parameters)
      const parsed = yaml.parse(result)

      expect(parsed.parameters[0].name).toBe('scorecard_id')
      // When a parameter is not in the parameters object, it gets undefined which YAML converts to null
      expect(parsed.parameters[0].value).toBeNull()
    })

    it('should handle parameters with different data types', () => {
      const templateYaml = `
parameters:
  - name: text_param
    type: text
  - name: number_param
    type: number
  - name: boolean_param
    type: boolean
  - name: date_param
    type: date
`

      const parameters = {
        text_param: 'hello world',
        number_param: 42,
        boolean_param: true,
        date_param: '2024-01-15'
      }

      const result = injectParameterValues(templateYaml, parameters)
      const parsed = yaml.parse(result)

      expect(parsed.parameters[0].value).toBe('hello world')
      expect(parsed.parameters[1].value).toBe(42)
      expect(parsed.parameters[2].value).toBe(true)
      expect(parsed.parameters[3].value).toBe('2024-01-15')
    })

    it('should handle optional parameters with null/undefined values', () => {
      const templateYaml = `
parameters:
  - name: optional_param
    type: text
    required: false
  - name: required_param
    type: text
    required: true
`

      const parameters = {
        optional_param: null,
        required_param: 'value'
      }

      const result = injectParameterValues(templateYaml, parameters)
      const parsed = yaml.parse(result)

      expect(parsed.parameters[0].value).toBeNull()
      expect(parsed.parameters[1].value).toBe('value')
    })

    it('should preserve YAML structure and formatting for non-parameter content', () => {
      const templateYaml = `
parameters:
  - name: scorecard_id
    type: scorecard_select

class: BeamSearch
value: |
  local score = experiment_node.value.accuracy or 0
  local penalty = (experiment_node.value.cost or 0) * 0.1
  return score - penalty

conversation_flow:
  initial_state: investigation
  states:
    investigation:
      description: Deep exploration
`

      const parameters = {
        scorecard_id: 'scorecard-123'
      }

      const result = injectParameterValues(templateYaml, parameters)
      const parsed = yaml.parse(result)

      expect(parsed.class).toBe('BeamSearch')
      expect(parsed.value).toContain('local score')
      expect(parsed.conversation_flow.initial_state).toBe('investigation')
      expect(parsed.conversation_flow.states.investigation.description).toBe('Deep exploration')
      expect(parsed.parameters[0].value).toBe('scorecard-123')
    })

    it('should handle invalid YAML gracefully', () => {
      const invalidYaml = `
parameters:
  - name: test
    invalid: [unclosed bracket
`

      const parameters = {
        test: 'value'
      }

      const result = injectParameterValues(invalidYaml, parameters)
      
      // Should return original YAML when parsing fails
      expect(result).toBe(invalidYaml)
    })

    it('should handle parameters with complex nested values', () => {
      const templateYaml = `
parameters:
  - name: config
    type: select
    options:
      - value: option1
        label: Option 1
      - value: option2
        label: Option 2
`

      const parameters = {
        config: 'option1'
      }

      const result = injectParameterValues(templateYaml, parameters)
      const parsed = yaml.parse(result)

      expect(parsed.parameters[0].value).toBe('option1')
      expect(parsed.parameters[0].options).toHaveLength(2)
      expect(parsed.parameters[0].options[0].value).toBe('option1')
    })
  })
})


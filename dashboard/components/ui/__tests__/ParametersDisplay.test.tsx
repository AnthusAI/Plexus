import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ParametersDisplay } from '../ParametersDisplay'
import type { ParameterDefinition, ParameterValues } from '@/types/parameters'

describe('ParametersDisplay', () => {
  it('renders without parameters', () => {
    const { container } = render(
      <ParametersDisplay
        parameters={[]}
        values={{}}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders text parameter value', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'project_name',
        label: 'Project Name',
        type: 'text',
        required: true
      }
    ]

    const values: ParameterValues = {
      project_name: 'Test Project'
    }

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    expect(screen.getByText('Project Name')).toBeInTheDocument()
    expect(screen.getByText('Test Project')).toBeInTheDocument()
  })

  it('renders number parameter value', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'max_iterations',
        label: 'Maximum Iterations',
        type: 'number',
        required: true
      }
    ]

    const values: ParameterValues = {
      max_iterations: 42
    }

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    expect(screen.getByText('Maximum Iterations')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders boolean parameter with checkmark for true', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'enable_debug',
        label: 'Enable Debug',
        type: 'boolean',
        default: false
      }
    ]

    const values: ParameterValues = {
      enable_debug: true
    }

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    expect(screen.getByText('Enable Debug')).toBeInTheDocument()
    expect(screen.getByText('Yes')).toBeInTheDocument()
  })

  it('renders boolean parameter with X for false', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'enable_debug',
        label: 'Enable Debug',
        type: 'boolean',
        default: false
      }
    ]

    const values: ParameterValues = {
      enable_debug: false
    }

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    expect(screen.getByText('No')).toBeInTheDocument()
  })

  it('renders select parameter with option label', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'environment',
        label: 'Environment',
        type: 'select',
        required: true,
        options: [
          { value: 'dev', label: 'Development' },
          { value: 'prod', label: 'Production' }
        ]
      }
    ]

    const values: ParameterValues = {
      environment: 'prod'
    }

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    expect(screen.getByText('Environment')).toBeInTheDocument()
    expect(screen.getByText('Production')).toBeInTheDocument()
    expect(screen.queryByText('prod')).not.toBeInTheDocument()
  })

  it('renders date parameter formatted', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'due_date',
        label: 'Due Date',
        type: 'date',
        required: false
      }
    ]

    const values: ParameterValues = {
      due_date: '2025-12-31'
    }

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    expect(screen.getByText('Due Date')).toBeInTheDocument()
    // The date formatting will vary by locale, so just check it's not the raw ISO format
    expect(screen.queryByText('2025-12-31')).not.toBeInTheDocument()
  })

  it('displays em dash for missing values', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'optional_field',
        label: 'Optional Field',
        type: 'text',
        required: false
      }
    ]

    const values: ParameterValues = {}

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    expect(screen.getByText('Optional Field')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('displays required indicator', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'required_field',
        label: 'Required Field',
        type: 'text',
        required: true
      },
      {
        name: 'optional_field',
        label: 'Optional Field',
        type: 'text',
        required: false
      }
    ]

    const values: ParameterValues = {
      required_field: 'value'
    }

    const { container } = render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    // Required field should have an asterisk
    const requiredLabel = screen.getByText('Required Field').parentElement
    expect(requiredLabel?.textContent).toContain('*')
  })

  it('renders in compact mode', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'field1',
        label: 'Field 1',
        type: 'text',
        required: true
      },
      {
        name: 'field2',
        label: 'Field 2',
        type: 'number',
        required: true
      }
    ]

    const values: ParameterValues = {
      field1: 'value1',
      field2: 42
    }

    const { container } = render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
        compact={true}
      />
    )

    // In compact mode, should not render Card
    expect(container.querySelector('[class*="card"]')).not.toBeInTheDocument()
    
    // Should show labels and values
    expect(screen.getByText(/Field 1:/)).toBeInTheDocument()
    expect(screen.getByText('value1')).toBeInTheDocument()
  })

  it('hides empty values in compact mode', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'field1',
        label: 'Field 1',
        type: 'text',
        required: true
      },
      {
        name: 'field2',
        label: 'Field 2',
        type: 'text',
        required: false
      }
    ]

    const values: ParameterValues = {
      field1: 'value1'
      // field2 is empty
    }

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
        compact={true}
      />
    )

    expect(screen.getByText(/Field 1:/)).toBeInTheDocument()
    expect(screen.queryByText(/Field 2:/)).not.toBeInTheDocument()
  })

  it('renders multiple parameters', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'text_field',
        label: 'Text Field',
        type: 'text',
        required: true
      },
      {
        name: 'number_field',
        label: 'Number Field',
        type: 'number',
        required: true
      },
      {
        name: 'boolean_field',
        label: 'Boolean Field',
        type: 'boolean',
        default: false
      }
    ]

    const values: ParameterValues = {
      text_field: 'Hello',
      number_field: 123,
      boolean_field: true
    }

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    expect(screen.getByText('Text Field')).toBeInTheDocument()
    expect(screen.getByText('Hello')).toBeInTheDocument()
    
    expect(screen.getByText('Number Field')).toBeInTheDocument()
    expect(screen.getByText('123')).toBeInTheDocument()
    
    expect(screen.getByText('Boolean Field')).toBeInTheDocument()
    expect(screen.getByText('Yes')).toBeInTheDocument()
  })

  it('handles partial values gracefully', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'field1',
        label: 'Field 1',
        type: 'text',
        required: true
      },
      {
        name: 'field2',
        label: 'Field 2',
        type: 'text',
        required: true
      },
      {
        name: 'field3',
        label: 'Field 3',
        type: 'text',
        required: false
      }
    ]

    const values: ParameterValues = {
      field1: 'value1'
      // field2 and field3 are missing
    }

    render(
      <ParametersDisplay
        parameters={parameters}
        values={values}
      />
    )

    expect(screen.getByText('value1')).toBeInTheDocument()
    
    // Should show em dash for missing values
    const emDashes = screen.getAllByText('—')
    expect(emDashes).toHaveLength(2)
  })
})


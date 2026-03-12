import React from 'react'
import { render, screen, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { ConfigurableParametersForm } from '../ConfigurableParametersForm'
import type { ParameterDefinition, ParameterValues } from '@/types/parameters'

// Mock the AccountContext
jest.mock('@/app/contexts/AccountContext', () => ({
  useAccount: () => ({
    selectedAccount: {
      id: 'test-account-123',
      name: 'Test Account'
    }
  })
}))

// Mock aws-amplify/data
jest.mock('aws-amplify/data', () => ({
  generateClient: jest.fn(() => ({
    graphql: jest.fn()
  }))
}))

describe('ConfigurableParametersForm', () => {
  const mockOnChange = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders without parameters', () => {
    const { container } = render(
      <ConfigurableParametersForm
        parameters={[]}
        values={{}}
        onChange={mockOnChange}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders text parameter', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'project_name',
        label: 'Project Name',
        type: 'text',
        required: true
      }
    ]

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{}}
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('Project Name')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('renders number parameter', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'max_iterations',
        label: 'Maximum Iterations',
        type: 'number',
        required: true,
        min: 1,
        max: 100
      }
    ]

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{}}
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('Maximum Iterations')).toBeInTheDocument()
    const input = screen.getByRole('spinbutton')
    expect(input).toHaveAttribute('min', '1')
    expect(input).toHaveAttribute('max', '100')
  })

  it('renders boolean parameter', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'enable_debug',
        label: 'Enable Debug',
        type: 'boolean',
        default: false
      }
    ]

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{}}
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('Enable Debug')).toBeInTheDocument()
    expect(screen.getByRole('checkbox')).toBeInTheDocument()
  })

  it('renders select parameter', () => {
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

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{}}
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('Environment')).toBeInTheDocument()
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('calls onChange when text input changes', async () => {
    const user = userEvent.setup()
    const parameters: ParameterDefinition[] = [
      {
        name: 'project_name',
        label: 'Project Name',
        type: 'text',
        required: true
      }
    ]

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{}}
        onChange={mockOnChange}
      />
    )

    const input = screen.getByRole('textbox')
    await user.type(input, 'Test Project')

    expect(mockOnChange).toHaveBeenCalled()
    const lastCall = mockOnChange.mock.calls[mockOnChange.mock.calls.length - 1]
    expect(lastCall[0]).toHaveProperty('project_name', 'Test Project')
  })

  it('calls onChange when number input changes', async () => {
    const user = userEvent.setup()
    const parameters: ParameterDefinition[] = [
      {
        name: 'count',
        label: 'Count',
        type: 'number',
        required: true
      }
    ]

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{}}
        onChange={mockOnChange}
      />
    )

    const input = screen.getByRole('spinbutton')
    await user.clear(input)
    await user.type(input, '42')

    expect(mockOnChange).toHaveBeenCalled()
    const lastCall = mockOnChange.mock.calls[mockOnChange.mock.calls.length - 1]
    expect(lastCall[0]).toHaveProperty('count', 42)
  })

  it('calls onChange when boolean input changes', async () => {
    const user = userEvent.setup()
    const parameters: ParameterDefinition[] = [
      {
        name: 'enable_debug',
        label: 'Enable Debug',
        type: 'boolean',
        default: false
      }
    ]

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{ enable_debug: false }}
        onChange={mockOnChange}
      />
    )

    const checkbox = screen.getByRole('checkbox')
    await user.click(checkbox)

    expect(mockOnChange).toHaveBeenCalledWith(
      expect.objectContaining({ enable_debug: true })
    )
  })

  it('displays error messages', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        required: true
      }
    ]

    const errors = {
      username: 'Username is required'
    }

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{}}
        onChange={mockOnChange}
        errors={errors}
      />
    )

    expect(screen.getByText('Username is required')).toBeInTheDocument()
  })

  it('handles dependent fields', async () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'category',
        label: 'Category',
        type: 'select',
        required: true,
        options: [
          { value: 'A', label: 'Category A' },
          { value: 'B', label: 'Category B' }
        ]
      },
      {
        name: 'subcategory',
        label: 'Subcategory',
        type: 'text',
        required: true,
        depends_on: 'category'
      }
    ]

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{}}
        onChange={mockOnChange}
      />
    )

    // Subcategory should be disabled initially
    const inputs = screen.getAllByRole('textbox')
    const subcategoryInput = inputs.find((input) => input.id === 'subcategory')
    expect(subcategoryInput).toBeDisabled()
  })

  it('clears dependent field when parent changes', async () => {
    const user = userEvent.setup()
    const parameters: ParameterDefinition[] = [
      {
        name: 'parent',
        label: 'Parent',
        type: 'text',
        required: true
      },
      {
        name: 'child',
        label: 'Child',
        type: 'text',
        required: false,
        depends_on: 'parent'
      }
    ]

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{ parent: 'A', child: 'X' }}
        onChange={mockOnChange}
      />
    )

    const inputs = screen.getAllByRole('textbox')
    const parentInput = inputs.find((input) => input.id === 'parent')!
    await user.clear(parentInput)
    await user.type(parentInput, 'B')

    // Should have called onChange with child cleared
    expect(mockOnChange).toHaveBeenCalled()
    const lastCall = mockOnChange.mock.calls[mockOnChange.mock.calls.length - 1]
    expect(lastCall[0]).toHaveProperty('parent', 'B')
    expect(lastCall[0]).toHaveProperty('child', undefined)
  })

  it('displays multiple parameters', () => {
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

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={{}}
        onChange={mockOnChange}
      />
    )

    expect(screen.getByText('Text Field')).toBeInTheDocument()
    expect(screen.getByText('Number Field')).toBeInTheDocument()
    expect(screen.getByText('Boolean Field')).toBeInTheDocument()
  })

  it('pre-fills values', () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'project_name',
        label: 'Project Name',
        type: 'text',
        required: true
      }
    ]

    const values = {
      project_name: 'Existing Project'
    }

    render(
      <ConfigurableParametersForm
        parameters={parameters}
        values={values}
        onChange={mockOnChange}
      />
    )

    const input = screen.getByRole('textbox') as HTMLInputElement
    expect(input.value).toBe('Existing Project')
  })
})


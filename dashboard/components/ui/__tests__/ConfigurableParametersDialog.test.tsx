import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, jest } from '@jest/globals'
import { ConfigurableParametersDialog } from '../ConfigurableParametersDialog'
import { ParameterDefinition } from '@/types/parameters'

// Mock vaul (drawer dependency)
jest.mock('vaul', () => ({
  Drawer: {
    Root: ({ children }: any) => <div>{children}</div>,
    Trigger: ({ children }: any) => <div>{children}</div>,
    Portal: ({ children }: any) => <div>{children}</div>,
    Overlay: ({ children }: any) => <div>{children}</div>,
    Content: ({ children }: any) => <div>{children}</div>,
    Title: ({ children }: any) => <div>{children}</div>,
    Description: ({ children }: any) => <div>{children}</div>,
    Close: ({ children }: any) => <div>{children}</div>,
  }
}))

// Mock the AccountContext
jest.mock('@/app/contexts/AccountContext', () => ({
  useAccount: () => ({
    selectedAccount: { id: 'test-account-id', name: 'Test Account' }
  })
}))

// Mock amplify client
jest.mock('aws-amplify/data', () => ({
  generateClient: () => ({
    models: {
      Scorecard: {
        list: jest.fn().mockResolvedValue({
          data: [
            { id: 'sc1', name: 'Scorecard 1' },
            { id: 'sc2', name: 'Scorecard 2' }
          ]
        })
      },
      Score: {
        list: jest.fn().mockResolvedValue({
          data: [
            { id: 's1', name: 'Score 1' },
            { id: 's2', name: 'Score 2' }
          ]
        })
      },
      ScoreVersion: {
        list: jest.fn().mockResolvedValue({
          data: [
            { id: 'sv1', createdAt: '2024-01-01', isFeatured: true },
            { id: 'sv2', createdAt: '2024-01-02', isFeatured: false }
          ]
        })
      }
    }
  })
}))

describe('ConfigurableParametersDialog', () => {
  it('should render with basic text parameters', () => {
    const parameters: ParameterDefinition[] = [
      { name: 'test_field', label: 'Test Field', type: 'text', required: true }
    ]

    render(
      <ConfigurableParametersDialog
        open={true}
        onOpenChange={() => {}}
        title="Test Dialog"
        parameters={parameters}
        onSubmit={() => {}}
      />
    )

    expect(screen.getByText('Test Dialog')).toBeInTheDocument()
    expect(screen.getByLabelText(/Test Field/)).toBeInTheDocument()
  })

  it('should show validation errors for required fields', async () => {
    const parameters: ParameterDefinition[] = [
      { name: 'required_field', label: 'Required Field', type: 'text', required: true }
    ]
    
    const onSubmit = jest.fn()

    render(
      <ConfigurableParametersDialog
        open={true}
        onOpenChange={() => {}}
        title="Test Dialog"
        parameters={parameters}
        onSubmit={onSubmit}
      />
    )

    const submitButton = screen.getByRole('button', { name: /Submit/ })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText(/Required Field is required/)).toBeInTheDocument()
    })
    
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('should call onSubmit with values when valid', async () => {
    const parameters: ParameterDefinition[] = [
      { name: 'name', label: 'Name', type: 'text', required: true }
    ]
    
    const onSubmit = jest.fn()

    render(
      <ConfigurableParametersDialog
        open={true}
        onOpenChange={() => {}}
        title="Test Dialog"
        parameters={parameters}
        onSubmit={onSubmit}
      />
    )

    const input = screen.getByLabelText(/Name/)
    fireEvent.change(input, { target: { value: 'Test Name' } })

    const submitButton = screen.getByRole('button', { name: /Submit/ })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ name: 'Test Name' })
    })
  })

  it('should handle number parameters with min/max validation', async () => {
    const parameters: ParameterDefinition[] = [
      { 
        name: 'age', 
        label: 'Age', 
        type: 'number', 
        required: true, 
        min: 18, 
        max: 65 
      }
    ]
    
    const onSubmit = jest.fn()

    render(
      <ConfigurableParametersDialog
        open={true}
        onOpenChange={() => {}}
        title="Test Dialog"
        parameters={parameters}
        onSubmit={onSubmit}
      />
    )

    const input = screen.getByLabelText(/Age/)
    
    // Test below min
    fireEvent.change(input, { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }))
    
    await waitFor(() => {
      expect(screen.getByText(/at least 18/)).toBeInTheDocument()
    })

    // Test valid value
    fireEvent.change(input, { target: { value: '30' } })
    fireEvent.click(screen.getByRole('button', { name: /Submit/ }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({ age: 30 })
    })
  })

  it('should handle boolean parameters', () => {
    const parameters: ParameterDefinition[] = [
      { name: 'agree', label: 'I agree', type: 'boolean', required: true }
    ]

    render(
      <ConfigurableParametersDialog
        open={true}
        onOpenChange={() => {}}
        title="Test Dialog"
        parameters={parameters}
        onSubmit={() => {}}
      />
    )

    const checkbox = screen.getByRole('checkbox')
    expect(checkbox).toBeInTheDocument()
    
    fireEvent.click(checkbox)
    expect(checkbox).toBeChecked()
  })

  it('should handle select parameters', () => {
    const parameters: ParameterDefinition[] = [
      { 
        name: 'country', 
        label: 'Country', 
        type: 'select',
        options: [
          { value: 'us', label: 'United States' },
          { value: 'uk', label: 'United Kingdom' }
        ]
      }
    ]

    render(
      <ConfigurableParametersDialog
        open={true}
        onOpenChange={() => {}}
        title="Test Dialog"
        parameters={parameters}
        onSubmit={() => {}}
      />
    )

    expect(screen.getByText('Country')).toBeInTheDocument()
  })

  it('should clear dependent fields when dependency changes', async () => {
    const parameters: ParameterDefinition[] = [
      { name: 'parent', label: 'Parent', type: 'text' },
      { name: 'child', label: 'Child', type: 'text', depends_on: 'parent' }
    ]
    
    const onSubmit = jest.fn()

    render(
      <ConfigurableParametersDialog
        open={true}
        onOpenChange={() => {}}
        title="Test Dialog"
        parameters={parameters}
        onSubmit={onSubmit}
      />
    )

    const parentInput = screen.getByLabelText(/Parent/)
    const childInput = screen.getByLabelText(/Child/)

    // Set both values
    fireEvent.change(parentInput, { target: { value: 'parent value' } })
    fireEvent.change(childInput, { target: { value: 'child value' } })

    // Change parent - child should be cleared
    fireEvent.change(parentInput, { target: { value: 'new parent' } })

    fireEvent.click(screen.getByRole('button', { name: /Submit/ }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        parent: 'new parent',
        child: ''
      })
    })
  })

  it('should initialize with default values', () => {
    const parameters: ParameterDefinition[] = [
      { name: 'field1', label: 'Field 1', type: 'text', default: 'default text' },
      { name: 'field2', label: 'Field 2', type: 'number', default: 42 },
      { name: 'field3', label: 'Field 3', type: 'boolean', default: true }
    ]

    render(
      <ConfigurableParametersDialog
        open={true}
        onOpenChange={() => {}}
        title="Test Dialog"
        parameters={parameters}
        onSubmit={() => {}}
      />
    )

    expect(screen.getByLabelText(/Field 1/)).toHaveValue('default text')
    expect(screen.getByLabelText(/Field 2/)).toHaveValue(42)
    expect(screen.getByRole('checkbox')).toBeChecked()
  })

  it('should use custom submit and cancel labels', () => {
    render(
      <ConfigurableParametersDialog
        open={true}
        onOpenChange={() => {}}
        title="Test Dialog"
        parameters={[]}
        onSubmit={() => {}}
        submitLabel="Create"
        cancelLabel="Abort"
      />
    )

    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Abort' })).toBeInTheDocument()
  })
})


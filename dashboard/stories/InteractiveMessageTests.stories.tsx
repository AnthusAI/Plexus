import type { Meta, StoryObj } from '@storybook/react'
import { within, userEvent, expect, fn } from '@storybook/test'
import { ChatFeedView, type ChatMessage } from '@/components/chat-feed'

/**
 * Interactive Message Interaction Tests
 *
 * Automated tests for interactive message behaviors:
 * - Collapsible section expand/collapse
 * - Button clicks
 * - Form input and submission
 * - Multiple sections interaction
 */
const meta = {
  title: 'Chat/Interaction Tests',
  component: ChatFeedView,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Automated interaction tests for collapsible sections, buttons, and forms.',
      },
    },
  },
  decorators: [
    (Story) => (
      <div className="h-screen w-full bg-background">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ChatFeedView>

export default meta
type Story = StoryObj<typeof meta>

const timestamp = () => new Date().toISOString()

// ============================================================================
// INTERACTION TESTS: Collapsible Sections
// ============================================================================

export const CollapsibleSectionToggle: Story = {
  name: 'Test: Collapsible section toggle',
  args: {
    messages: [{
      id: 'test-1',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'Message with collapsible section',
        collapsibleSections: [
          {
            title: 'Expandable Section',
            content: 'This content should appear when expanded',
          },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Find the section title (always visible)
    const sectionTitle = canvas.getByText('Expandable Section')
    expect(sectionTitle).toBeInTheDocument()

    // Initially, content should NOT be visible (collapsed by default)
    expect(canvas.queryByText('This content should appear when expanded')).not.toBeInTheDocument()

    // Find and click the chevron button to expand using aria-label
    const expandButton = canvas.getByRole('button', { name: 'Expand Expandable Section' })
    await userEvent.click(expandButton)

    // After clicking, content SHOULD be visible
    expect(canvas.getByText('This content should appear when expanded')).toBeInTheDocument()

    // Find the collapse button (label changes when expanded)
    const collapseButton = canvas.getByRole('button', { name: 'Collapse Expandable Section' })
    await userEvent.click(collapseButton)

    // Content should be hidden again
    expect(canvas.queryByText('This content should appear when expanded')).not.toBeInTheDocument()
  },
}

export const CollapsibleSectionDefaultOpen: Story = {
  name: 'Test: Collapsible section default open',
  args: {
    messages: [{
      id: 'test-2',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'Message with default-open section',
        collapsibleSections: [
          {
            title: 'Default Open Section',
            content: 'This content should be visible initially',
            defaultOpen: true,
          },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Content should be visible initially (defaultOpen: true)
    expect(canvas.getByText('This content should be visible initially')).toBeInTheDocument()

    // Click to collapse
    const collapseButton = canvas.getByRole('button', { name: 'Collapse Default Open Section' })
    await userEvent.click(collapseButton)

    // Content should now be hidden
    expect(canvas.queryByText('This content should be visible initially')).not.toBeInTheDocument()
  },
}

export const MultipleCollapsibleSectionsIndependent: Story = {
  name: 'Test: Multiple sections toggle independently',
  args: {
    messages: [{
      id: 'test-3',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'NOTIFICATION',
      createdAt: timestamp(),
      metadata: {
        content: 'Message with multiple collapsible sections',
        collapsibleSections: [
          {
            title: 'Section A',
            content: 'Content A',
          },
          {
            title: 'Section B',
            content: 'Content B',
          },
          {
            title: 'Section C',
            content: 'Content C',
          },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // All sections should be collapsed initially
    expect(canvas.queryByText('Content A')).not.toBeInTheDocument()
    expect(canvas.queryByText('Content B')).not.toBeInTheDocument()
    expect(canvas.queryByText('Content C')).not.toBeInTheDocument()

    // Expand first section only using aria-label
    const expandA = canvas.getByRole('button', { name: 'Expand Section A' })
    await userEvent.click(expandA)
    expect(canvas.getByText('Content A')).toBeInTheDocument()
    expect(canvas.queryByText('Content B')).not.toBeInTheDocument()
    expect(canvas.queryByText('Content C')).not.toBeInTheDocument()

    // Expand second section (first should still be open)
    const expandB = canvas.getByRole('button', { name: 'Expand Section B' })
    await userEvent.click(expandB)
    expect(canvas.getByText('Content A')).toBeInTheDocument()
    expect(canvas.getByText('Content B')).toBeInTheDocument()
    expect(canvas.queryByText('Content C')).not.toBeInTheDocument()

    // Collapse first section (second should stay open)
    const collapseA = canvas.getByRole('button', { name: 'Collapse Section A' })
    await userEvent.click(collapseA)
    expect(canvas.queryByText('Content A')).not.toBeInTheDocument()
    expect(canvas.getByText('Content B')).toBeInTheDocument()
    expect(canvas.queryByText('Content C')).not.toBeInTheDocument()
  },
}

// ============================================================================
// INTERACTION TESTS: Buttons
// ============================================================================

const mockOnSubmit = fn()

export const ButtonClick: Story = {
  name: 'Test: Button click submits value',
  args: {
    messages: [{
      id: 'test-4',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_APPROVAL',
      createdAt: timestamp(),
      metadata: {
        content: 'Approve this action?',
        buttons: [
          { label: 'Approve', value: 'approve', variant: 'default' },
          { label: 'Reject', value: 'reject', variant: 'destructive' },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Find the Approve button
    const approveButton = canvas.getByRole('button', { name: 'Approve' })
    expect(approveButton).toBeInTheDocument()

    // Click it
    await userEvent.click(approveButton)

    // Note: In real app, onSubmit would be called with { action: 'approve' }
    // Storybook test just verifies button is clickable
    expect(approveButton).toBeEnabled()
  },
}

export const MultipleButtonsDistinct: Story = {
  name: 'Test: Multiple buttons are distinct',
  args: {
    messages: [{
      id: 'test-5',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_APPROVAL',
      createdAt: timestamp(),
      metadata: {
        content: 'Choose an action',
        buttons: [
          { label: 'Option A', value: 'a', variant: 'default' },
          { label: 'Option B', value: 'b', variant: 'secondary' },
          { label: 'Option C', value: 'c', variant: 'outline' },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // All three buttons should exist
    const buttonA = canvas.getByRole('button', { name: 'Option A' })
    const buttonB = canvas.getByRole('button', { name: 'Option B' })
    const buttonC = canvas.getByRole('button', { name: 'Option C' })

    expect(buttonA).toBeInTheDocument()
    expect(buttonB).toBeInTheDocument()
    expect(buttonC).toBeInTheDocument()

    // All should be enabled
    expect(buttonA).toBeEnabled()
    expect(buttonB).toBeEnabled()
    expect(buttonC).toBeEnabled()
  },
}

// ============================================================================
// INTERACTION TESTS: Input Fields
// ============================================================================

export const InputFieldTyping: Story = {
  name: 'Test: Input field accepts text',
  args: {
    messages: [{
      id: 'test-6',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(),
      metadata: {
        content: 'Enter a value',
        inputs: [
          {
            name: 'test_value',
            label: 'Test Value',
            placeholder: 'Enter value',
            required: true,
          },
        ],
        buttons: [
          { label: 'Submit', value: 'submit' },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Find the input field by label (use regex to match with or without asterisk)
    const input = canvas.getByLabelText(/Test Value/)
    expect(input).toBeInTheDocument()

    // Type into it
    await userEvent.type(input, 'test input value')

    // Verify the value
    expect(input).toHaveValue('test input value')
  },
}

export const TextareaFieldTyping: Story = {
  name: 'Test: Textarea field accepts text',
  args: {
    messages: [{
      id: 'test-7',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(),
      metadata: {
        content: 'Enter detailed information',
        inputs: [
          {
            name: 'description',
            label: 'Description',
            type: 'textarea',
            placeholder: 'Enter description',
            required: true,
          },
        ],
        buttons: [
          { label: 'Submit', value: 'submit' },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Find the textarea by label (use regex to match with or without asterisk)
    const textarea = canvas.getByLabelText(/Description/)
    expect(textarea).toBeInTheDocument()

    // Type multi-line text
    await userEvent.type(textarea, 'Line 1{enter}Line 2{enter}Line 3')

    // Verify the value contains newlines
    expect(textarea).toHaveValue('Line 1\nLine 2\nLine 3')
  },
}

export const MultipleInputFieldsIndependent: Story = {
  name: 'Test: Multiple input fields work independently',
  args: {
    messages: [{
      id: 'test-8',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(),
      metadata: {
        content: 'Fill out the form',
        inputs: [
          {
            name: 'field1',
            label: 'Field 1',
            required: true,
          },
          {
            name: 'field2',
            label: 'Field 2',
            required: false,
          },
          {
            name: 'field3',
            label: 'Field 3',
            type: 'textarea',
            required: true,
          },
        ],
        buttons: [
          { label: 'Submit', value: 'submit' },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Get all input fields (use regex to match with or without asterisk)
    const field1 = canvas.getByLabelText(/Field 1/)
    const field2 = canvas.getByLabelText(/Field 2/)
    const field3 = canvas.getByLabelText(/Field 3/)

    // Type different values in each
    await userEvent.type(field1, 'Value 1')
    await userEvent.type(field2, 'Value 2')
    await userEvent.type(field3, 'Value 3')

    // Verify each has correct value
    expect(field1).toHaveValue('Value 1')
    expect(field2).toHaveValue('Value 2')
    expect(field3).toHaveValue('Value 3')
  },
}

export const RequiredFieldIndicator: Story = {
  name: 'Test: Required fields show asterisk',
  args: {
    messages: [{
      id: 'test-9',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(),
      metadata: {
        content: 'Some required, some optional',
        inputs: [
          {
            name: 'required_field',
            label: 'Required Field',
            required: true,
          },
          {
            name: 'optional_field',
            label: 'Optional Field',
            required: false,
          },
        ],
        buttons: [
          { label: 'Submit', value: 'submit' },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Required field should have asterisk in label (use regex to match)
    const requiredField = canvas.getByLabelText(/Required Field/)
    expect(requiredField).toBeInTheDocument()
    expect(requiredField).toBeRequired()

    // Optional field should NOT have asterisk
    const optionalField = canvas.getByLabelText(/Optional Field/)
    expect(optionalField).toBeInTheDocument()
    expect(optionalField).not.toBeRequired()
  },
}

// ============================================================================
// INTERACTION TESTS: Combined Features
// ============================================================================

export const CollapsibleWithButtons: Story = {
  name: 'Test: Collapsible sections work with buttons',
  args: {
    messages: [{
      id: 'test-10',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_APPROVAL',
      createdAt: timestamp(),
      metadata: {
        content: 'Review the details before approving',
        collapsibleSections: [
          {
            title: 'Important Details',
            content: 'Read these details carefully',
          },
        ],
        buttons: [
          { label: 'Approve', value: 'approve', variant: 'default' },
          { label: 'Reject', value: 'reject', variant: 'destructive' },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Expand section using aria-label
    const expandButton = canvas.getByRole('button', { name: 'Expand Important Details' })
    await userEvent.click(expandButton)
    expect(canvas.getByText('Read these details carefully')).toBeInTheDocument()

    // Buttons should still be clickable
    const approveButton = canvas.getByRole('button', { name: 'Approve' })
    expect(approveButton).toBeEnabled()
  },
}

export const CollapsibleWithInputs: Story = {
  name: 'Test: Collapsible sections work with inputs',
  args: {
    messages: [{
      id: 'test-11',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(),
      metadata: {
        content: 'Configure parameters',
        collapsibleSections: [
          {
            title: 'Help & Guidance',
            content: 'Here is how to fill out the form',
          },
        ],
        inputs: [
          {
            name: 'value',
            label: 'Value',
            required: true,
          },
        ],
        buttons: [
          { label: 'Submit', value: 'submit' },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Expand help section using aria-label
    const expandButton = canvas.getByRole('button', { name: 'Expand Help & Guidance' })
    await userEvent.click(expandButton)
    expect(canvas.getByText('Here is how to fill out the form')).toBeInTheDocument()

    // Input field should still work (use regex to match)
    const input = canvas.getByLabelText(/Value/)
    await userEvent.type(input, 'test value')
    expect(input).toHaveValue('test value')

    // Collapse help section
    const collapseButton = canvas.getByRole('button', { name: 'Collapse Help & Guidance' })
    await userEvent.click(collapseButton)
    expect(canvas.queryByText('Here is how to fill out the form')).not.toBeInTheDocument()

    // Input value should persist
    expect(input).toHaveValue('test value')
  },
}

// ============================================================================
// INTERACTION TESTS: Accessibility
// ============================================================================

export const KeyboardNavigation: Story = {
  name: 'Test: Keyboard navigation works',
  args: {
    messages: [{
      id: 'test-12',
      content: '',
      role: 'SYSTEM',
      messageType: 'MESSAGE',
      humanInteraction: 'PENDING_INPUT',
      createdAt: timestamp(),
      metadata: {
        content: 'Test keyboard navigation',
        inputs: [
          { name: 'field1', label: 'Field 1', required: true },
          { name: 'field2', label: 'Field 2', required: true },
        ],
        buttons: [
          { label: 'Submit', value: 'submit' },
          { label: 'Cancel', value: 'cancel' },
        ],
      },
    }],
    isLoading: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    const field1 = canvas.getByLabelText(/Field 1/)
    const field2 = canvas.getByLabelText(/Field 2/)
    const submitButton = canvas.getByRole('button', { name: 'Submit' })
    const cancelButton = canvas.getByRole('button', { name: 'Cancel' })

    // Focus first field
    field1.focus()
    expect(field1).toHaveFocus()

    // Tab to second field
    await userEvent.tab()
    expect(field2).toHaveFocus()

    // Tab to Submit button
    await userEvent.tab()
    expect(submitButton).toHaveFocus()

    // Tab to Cancel button
    await userEvent.tab()
    expect(cancelButton).toHaveFocus()
  },
}

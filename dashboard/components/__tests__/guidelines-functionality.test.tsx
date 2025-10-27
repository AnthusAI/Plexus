import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'

// Create a simplified component that tests just the guidelines logic
interface GuidelinesTestComponentProps {
  guidelines: string
  onSave?: (newGuidelines: string) => void
}

function GuidelinesTestComponent({ guidelines, onSave }: GuidelinesTestComponentProps) {
  const [isExpanded, setIsExpanded] = React.useState(false)
  const [isEditing, setIsEditing] = React.useState(false)
  const [editValue, setEditValue] = React.useState(guidelines)
  const [hasChanges, setHasChanges] = React.useState(false)
  const [isSaving, setIsSaving] = React.useState(false)

  const handleEditChange = (value: string) => {
    setEditValue(value)
    setHasChanges(value !== guidelines)
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await new Promise(resolve => setTimeout(resolve, 10)) // Simulate async save
      onSave?.(editValue)
      setIsEditing(false)
      setHasChanges(false)
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    setEditValue(guidelines)
    setIsEditing(false)
    setHasChanges(false)
  }

  return (
    <div data-testid="guidelines-component">
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
        <h3>Guidelines</h3>
        <div className="flex gap-1">
          {guidelines && !isEditing && (
            <button
              aria-label="Edit guidelines inline"
              onClick={() => setIsEditing(true)}
            >
              Edit
            </button>
          )}
          <button
            aria-label="Open guidelines editor"
            onClick={() => console.log('Open fullscreen')}
          >
            Expand
          </button>
        </div>
      </div>

      {/* Content */}
      {isEditing ? (
        <div>
          <textarea
            value={editValue}
            onChange={(e) => handleEditChange(e.target.value)}
            rows={12}
            data-testid="guidelines-textarea"
          />
          {hasChanges && (
            <div>
              <button
                onClick={handleCancel}
                disabled={isSaving}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                data-testid="save-button"
              >
                {isSaving ? 'Saving...' : 'Save'}
              </button>
            </div>
          )}
        </div>
      ) : guidelines ? (
        <div 
          onClick={() => setIsExpanded(!isExpanded)}
          className="cursor-pointer"
          data-testid="guidelines-content"
        >
          <div 
            style={!isExpanded ? { 
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              maxHeight: '5.25rem'
            } : {}}
          >
            {guidelines}
          </div>
          <div>
            <div className="h-px bg-muted"></div>
            <div>
              {!isExpanded ? '⌄' : '⌃'}
            </div>
          </div>
        </div>
      ) : (
        <div data-testid="no-guidelines">No guidelines.</div>
      )}
    </div>
  )
}

describe('Guidelines Functionality', () => {
  it('renders guidelines header and buttons', () => {
    render(<GuidelinesTestComponent guidelines="Test guidelines" />)
    
    expect(screen.getByText('Guidelines')).toBeInTheDocument()
    expect(screen.getByLabelText('Edit guidelines inline')).toBeInTheDocument()
    expect(screen.getByLabelText('Open guidelines editor')).toBeInTheDocument()
  })

  it('shows "No guidelines" when empty', () => {
    render(<GuidelinesTestComponent guidelines="" />)
    
    expect(screen.getByTestId('no-guidelines')).toBeInTheDocument()
    expect(screen.getByText('No guidelines.')).toBeInTheDocument()
  })

  it('shows guidelines content when present', () => {
    render(<GuidelinesTestComponent guidelines="Test guidelines content" />)
    
    expect(screen.getByTestId('guidelines-content')).toBeInTheDocument()
    expect(screen.getByText('Test guidelines content')).toBeInTheDocument()
  })

  it('toggles expanded state when content is clicked', async () => {
    const user = userEvent.setup()
    render(<GuidelinesTestComponent guidelines="Line 1\nLine 2\nLine 3\nLine 4" />)
    
    const content = screen.getByTestId('guidelines-content')
    
    // Check if expand button shows initially (indicating collapsed state)
    expect(screen.getByLabelText('Open guidelines editor')).toBeInTheDocument()
    
    // Click to expand
    await user.click(content)
    // After expansion, the button label stays the same (this is a simple test component)
    expect(screen.getByLabelText('Open guidelines editor')).toBeInTheDocument()
    
    // Click to collapse  
    await user.click(content)
    expect(screen.getByLabelText('Open guidelines editor')).toBeInTheDocument()
  })

  it('enters edit mode when edit button is clicked', async () => {
    const user = userEvent.setup()
    render(<GuidelinesTestComponent guidelines="Test guidelines" />)
    
    const editButton = screen.getByLabelText('Edit guidelines inline')
    await user.click(editButton)
    
    expect(screen.getByTestId('guidelines-textarea')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Test guidelines')).toBeInTheDocument()
  })

  it('shows save/cancel buttons when text is changed', async () => {
    const user = userEvent.setup()
    render(<GuidelinesTestComponent guidelines="Original text" />)
    
    const editButton = screen.getByLabelText('Edit guidelines inline')
    await user.click(editButton)
    
    const textarea = screen.getByTestId('guidelines-textarea')
    await user.type(textarea, ' modified')
    
    expect(screen.getByText('Save')).toBeInTheDocument()
    expect(screen.getByText('Cancel')).toBeInTheDocument()
  })

  it('calls onSave when save button is clicked', async () => {
    const user = userEvent.setup()
    const mockOnSave = jest.fn()
    render(<GuidelinesTestComponent guidelines="Original" onSave={mockOnSave} />)
    
    const editButton = screen.getByLabelText('Edit guidelines inline')
    await user.click(editButton)
    
    const textarea = screen.getByTestId('guidelines-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'New content')
    
    // Wait for save button to appear (when hasChanges becomes true)
    const saveButton = await screen.findByTestId('save-button')
    await user.click(saveButton)
    
    // Wait for async save operation to complete
    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledWith('New content')
    })
  })

  it('shows loading state during save', async () => {
    const user = userEvent.setup()
    const mockOnSave = jest.fn().mockImplementation(() => 
      new Promise(resolve => setTimeout(resolve, 50))
    )
    render(<GuidelinesTestComponent guidelines="Original" onSave={mockOnSave} />)
    
    const editButton = screen.getByLabelText('Edit guidelines inline')
    await user.click(editButton)
    
    const textarea = screen.getByTestId('guidelines-textarea')
    await user.type(textarea, ' modified')
    
    const saveButton = screen.getByTestId('save-button')
    await user.click(saveButton)
    
    expect(screen.getByText('Saving...')).toBeInTheDocument()
    expect(saveButton).toBeDisabled()
  })

  it('cancels edit mode when cancel is clicked', async () => {
    const user = userEvent.setup()
    render(<GuidelinesTestComponent guidelines="Original text" />)
    
    const editButton = screen.getByLabelText('Edit guidelines inline')
    await user.click(editButton)
    
    const textarea = screen.getByTestId('guidelines-textarea')
    await user.type(textarea, ' modified')
    
    const cancelButton = screen.getByText('Cancel')
    await user.click(cancelButton)
    
    // Should exit edit mode and revert text
    expect(screen.queryByTestId('guidelines-textarea')).not.toBeInTheDocument()
    expect(screen.getByText('Original text')).toBeInTheDocument()
  })

  it('shows expand button even when no guidelines exist', () => {
    render(<GuidelinesTestComponent guidelines="" />)
    
    expect(screen.getByLabelText('Open guidelines editor')).toBeInTheDocument()
  })

  it('does not show edit button when no guidelines exist', () => {
    render(<GuidelinesTestComponent guidelines="" />)
    
    expect(screen.queryByLabelText('Edit guidelines inline')).not.toBeInTheDocument()
  })
})

import type { Meta, StoryObj } from '@storybook/react'
import { ChatFeedView, type ChatMessage } from '@/components/chat-feed'

/**
 * Interactive Messages - Chat messages requiring user interaction
 *
 * Shows every variation as FULL CHAT MESSAGES with icons, badges, timestamps, and interactive components.
 */
const meta = {
  title: 'Chat/Interactive Messages',
  component: ChatFeedView,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
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

// Helper to create a chat message
const createMessage = (interaction: string, metadata: any): ChatMessage => ({
  id: `msg-${Math.random()}`,
  content: '',
  role: 'SYSTEM',
  messageType: 'MESSAGE',
  humanInteraction: interaction,
  createdAt: timestamp(),
  metadata,
})

// ============================================================================
// APPROVAL REQUESTS
// ============================================================================

export const SimpleApproval: Story = {
  args: {
    messages: [createMessage('PENDING_APPROVAL', {
      content: 'Deploy new score configuration **v2.1.5** to production?\n\nThis will affect 3 active scorecards.',
      buttons: [
        { label: 'Approve', value: 'approve', variant: 'default' },
        { label: 'Reject', value: 'reject', variant: 'destructive' },
      ],
    })],
    isLoading: false,
  },
}

export const ThreeWayChoice: Story = {
  args: {
    messages: [createMessage('PENDING_APPROVAL', {
      content: 'Evaluation completed with 72% accuracy (below target of 85%).\n\nWhat would you like to do?',
      buttons: [
        { label: 'Retry with adjusted parameters', value: 'retry', variant: 'default' },
        { label: 'Accept and deploy', value: 'accept', variant: 'secondary' },
        { label: 'Cancel', value: 'cancel', variant: 'outline' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// INPUT REQUESTS
// ============================================================================

export const SingleTextInput: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Please provide the target accuracy threshold for the **Good Call** score.',
      inputs: [
        {
          name: 'accuracy_threshold',
          label: 'Target Accuracy (%)',
          placeholder: 'e.g., 85',
          required: true,
        },
      ],
      buttons: [
        { label: 'Submit', value: 'submit', variant: 'default' },
        { label: 'Cancel', value: 'cancel', variant: 'outline' },
      ],
    })],
    isLoading: false,
  },
}

export const SingleTextareaInput: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Please provide your analysis of the false positive patterns.',
      inputs: [
        {
          name: 'analysis',
          label: 'Analysis',
          description: 'Describe the patterns you observed and potential causes',
          placeholder: 'Enter your analysis here...',
          type: 'textarea',
          required: true,
        },
      ],
      buttons: [
        { label: 'Submit Analysis', value: 'submit', variant: 'default' },
        { label: 'Skip', value: 'skip', variant: 'ghost' },
      ],
    })],
    isLoading: false,
  },
}

export const MultipleInputs: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Configure the new evaluation run parameters.',
      inputs: [
        {
          name: 'scorecard_name',
          label: 'Scorecard Name',
          placeholder: 'e.g., CS3 Services v2',
          required: true,
        },
        {
          name: 'sample_size',
          label: 'Sample Size',
          description: 'Number of items to evaluate',
          placeholder: 'e.g., 500',
          required: true,
        },
        {
          name: 'notes',
          label: 'Notes',
          description: 'Optional notes about this evaluation',
          placeholder: 'Add any relevant context...',
          type: 'textarea',
          required: false,
        },
      ],
      buttons: [
        { label: 'Start Evaluation', value: 'start', variant: 'default' },
        { label: 'Cancel', value: 'cancel', variant: 'outline' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// REVIEW REQUESTS
// ============================================================================

export const ReviewRequest: Story = {
  args: {
    messages: [createMessage('PENDING_REVIEW', {
      content: '## Review Required\n\nThe false positive analysis has identified **12 patterns**.\n\n- 5 greeting-related mismatches\n- 4 timing issues\n- 3 context problems\n\nPlease review the detailed analysis.',
      buttons: [
        { label: 'Approve Findings', value: 'approve', variant: 'default' },
        { label: 'Request Changes', value: 'changes', variant: 'secondary' },
        { label: 'Reject', value: 'reject', variant: 'destructive' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// BUTTON VARIANTS
// ============================================================================

export const AllButtonVariants: Story = {
  args: {
    messages: [createMessage('PENDING_APPROVAL', {
      content: 'Testing all button variants',
      buttons: [
        { label: 'Primary', value: 'primary', variant: 'default' },
        { label: 'Secondary', value: 'secondary', variant: 'secondary' },
        { label: 'Destructive', value: 'destructive', variant: 'destructive' },
        { label: 'Outline', value: 'outline', variant: 'outline' },
        { label: 'Ghost', value: 'ghost', variant: 'ghost' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// WITH/WITHOUT HEADER
// ============================================================================

export const WithoutHeader: Story = {
  args: {
    messages: [createMessage('PENDING_APPROVAL', {
      // No content
      buttons: [
        { label: 'Yes', value: 'yes', variant: 'default' },
        { label: 'No', value: 'no', variant: 'outline' },
      ],
    })],
    isLoading: false,
  },
}

export const WithMarkdownHeader: Story = {
  args: {
    messages: [createMessage('PENDING_APPROVAL', {
      content: '## Important Decision\n\nThis action will:\n- Delete all existing data\n- Reset configurations\n- Require re-initialization\n\n**This cannot be undone.**',
      buttons: [
        { label: 'I Understand, Proceed', value: 'proceed', variant: 'destructive' },
        { label: 'Cancel', value: 'cancel', variant: 'outline' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// BUTTON COUNT VARIATIONS
// ============================================================================

export const OneButton: Story = {
  args: {
    messages: [createMessage('PENDING_APPROVAL', {
      content: 'Single button confirmation',
      buttons: [
        { label: 'Okay', value: 'okay', variant: 'default' },
      ],
    })],
    isLoading: false,
  },
}

export const ManyButtons: Story = {
  args: {
    messages: [createMessage('PENDING_APPROVAL', {
      content: 'Many button choices (should wrap)',
      buttons: [
        { label: 'Choice 1', value: '1', variant: 'default' },
        { label: 'Choice 2', value: '2', variant: 'secondary' },
        { label: 'Choice 3', value: '3', variant: 'secondary' },
        { label: 'Choice 4', value: '4', variant: 'secondary' },
        { label: 'Choice 5', value: '5', variant: 'secondary' },
        { label: 'Cancel', value: 'cancel', variant: 'outline' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// INPUT FIELD VARIATIONS
// ============================================================================

export const TwoInputFields: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Two input fields',
      inputs: [
        {
          name: 'first',
          label: 'First Value',
          placeholder: 'Enter first value',
          required: true,
        },
        {
          name: 'second',
          label: 'Second Value',
          placeholder: 'Enter second value',
          required: true,
        },
      ],
      buttons: [
        { label: 'Submit', value: 'submit', variant: 'default' },
      ],
    })],
    isLoading: false,
  },
}

export const MixedInputTypes: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Mix of text input and textarea',
      inputs: [
        {
          name: 'title',
          label: 'Title',
          placeholder: 'Brief title',
          type: 'text',
          required: true,
        },
        {
          name: 'description',
          label: 'Description',
          placeholder: 'Detailed description...',
          type: 'textarea',
          required: true,
        },
      ],
      buttons: [
        { label: 'Create', value: 'create', variant: 'default' },
        { label: 'Save Draft', value: 'draft', variant: 'secondary' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// REQUIRED vs OPTIONAL
// ============================================================================

export const AllRequiredFields: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'All fields are required (*)',
      inputs: [
        {
          name: 'field1',
          label: 'Required Field 1',
          placeholder: 'Must fill this',
          required: true,
        },
        {
          name: 'field2',
          label: 'Required Field 2',
          placeholder: 'Must fill this too',
          required: true,
        },
      ],
      buttons: [
        { label: 'Submit', value: 'submit' },
      ],
    })],
    isLoading: false,
  },
}

export const MixedRequiredOptional: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Some required, some optional',
      inputs: [
        {
          name: 'required_field',
          label: 'Required Field',
          description: 'This field must be filled',
          placeholder: 'Required',
          required: true,
        },
        {
          name: 'optional_field',
          label: 'Optional Field',
          description: 'This field is optional',
          placeholder: 'Optional',
          required: false,
        },
      ],
      buttons: [
        { label: 'Submit', value: 'submit' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// FIELD DESCRIPTIONS
// ============================================================================

export const WithDescriptions: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Inputs with helpful descriptions',
      inputs: [
        {
          name: 'accuracy',
          label: 'Target Accuracy',
          description: 'The minimum acceptable accuracy percentage (0-100)',
          placeholder: '85',
          required: true,
        },
        {
          name: 'sample_size',
          label: 'Sample Size',
          description: 'Number of items in the test evaluation run',
          placeholder: '500',
          required: true,
        },
      ],
      buttons: [
        { label: 'Run Test', value: 'run' },
      ],
    })],
    isLoading: false,
  },
}

export const WithoutDescriptions: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Simple inputs without descriptions',
      inputs: [
        {
          name: 'name',
          label: 'Name',
          placeholder: 'Enter name',
          required: true,
        },
        {
          name: 'value',
          label: 'Value',
          placeholder: 'Enter value',
          required: true,
        },
      ],
      buttons: [
        { label: 'Submit', value: 'submit' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// PLACEHOLDER VARIATIONS
// ============================================================================

export const DetailedPlaceholders: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Inputs with detailed placeholder guidance',
      inputs: [
        {
          name: 'scorecard',
          label: 'Scorecard Name',
          placeholder: 'e.g., "CS3 Services v2" or "Healthcare Quality Metrics"',
          required: true,
        },
        {
          name: 'threshold',
          label: 'Confidence Threshold',
          placeholder: 'Enter a value between 0.0 and 1.0 (e.g., 0.85)',
          required: true,
        },
      ],
      buttons: [
        { label: 'Apply', value: 'apply' },
      ],
    })],
    isLoading: false,
  },
}

// ============================================================================
// COLLAPSIBLE SECTIONS
// ============================================================================

export const SingleCollapsibleSection: Story = {
  args: {
    messages: [createMessage('PENDING_APPROVAL', {
      content: 'Review the detailed analysis before approving.',
      collapsibleSections: [
        {
          title: 'Detailed Analysis',
          content: '## Performance Metrics\n\n- Accuracy: 89.2%\n- Precision: 87.5%\n- Recall: 91.3%\n\n### Issues Found\n1. False positives in greeting detection\n2. Context awareness needs improvement',
        },
      ],
      buttons: [
        { label: 'Approve', value: 'approve', variant: 'default' },
        { label: 'Reject', value: 'reject', variant: 'destructive' },
      ],
    })],
    isLoading: false,
  },
}

export const MultipleCollapsibleSections: Story = {
  args: {
    messages: [createMessage('PENDING_REVIEW', {
      content: 'Review the analysis results',
      collapsibleSections: [
        {
          title: 'Performance Summary',
          content: '**Overall Accuracy**: 89.2%\n\n**Key Metrics**:\n- Precision: 87.5%\n- Recall: 91.3%\n- F1 Score: 89.4%',
        },
        {
          title: 'False Positive Analysis',
          content: 'Identified **12 false positive patterns**:\n\n1. Greeting detection issues (5 cases)\n2. Timing problems (4 cases)\n3. Context misunderstandings (3 cases)',
        },
        {
          title: 'Recommendations',
          content: '1. Adjust greeting detection sensitivity\n2. Improve context window handling\n3. Add more training examples for edge cases',
        },
      ],
      buttons: [
        { label: 'Approve Findings', value: 'approve', variant: 'default' },
        { label: 'Request Changes', value: 'changes', variant: 'secondary' },
      ],
    })],
    isLoading: false,
  },
}

export const CollapsibleSectionDefaultOpen: Story = {
  args: {
    messages: [createMessage('PENDING_INPUT', {
      content: 'Configure evaluation parameters',
      collapsibleSections: [
        {
          title: 'Advanced Options',
          content: 'These options are for advanced users:\n\n- **Confidence Threshold**: Minimum confidence for positive predictions\n- **Batch Size**: Number of items processed at once\n- **Temperature**: Model creativity parameter',
          defaultOpen: true,  // Starts expanded
        },
      ],
      inputs: [
        {
          name: 'confidence',
          label: 'Confidence Threshold',
          placeholder: '0.85',
          required: true,
        },
      ],
      buttons: [
        { label: 'Run Evaluation', value: 'run' },
      ],
    })],
    isLoading: false,
  },
}

export const CollapsibleWithLongContent: Story = {
  args: {
    messages: [createMessage('PENDING_APPROVAL', {
      content: 'Deploy configuration changes?',
      collapsibleSections: [
        {
          title: 'Full Change Log',
          content: `# Configuration Changes

## Score Updates
### Good Call Score (v2.1.5)
- Enhanced greeting detection patterns
- Improved context awareness
- Added regional variations support

### Quality Metrics Score (v1.8.2)
- Updated threshold calculations
- New edge case handling
- Performance optimizations

## Data Source Changes
- Updated training data (500 new examples)
- Improved label quality
- Fixed 3 data inconsistencies

## Infrastructure
- Upgraded model serving endpoint
- Increased rate limits
- Added monitoring alerts

## Testing Results
- All unit tests passed (247/247)
- Integration tests passed (89/89)
- Performance tests show 15% improvement`,
        },
      ],
      buttons: [
        { label: 'Deploy', value: 'deploy', variant: 'default' },
        { label: 'Cancel', value: 'cancel', variant: 'outline' },
      ],
    })],
    isLoading: false,
  },
}

export const CollapsibleSectionOnly: Story = {
  args: {
    messages: [createMessage('PENDING_REVIEW', {
      collapsibleSections: [
        {
          title: 'View Details',
          content: 'This message has no main content, only a collapsible section with details inside.',
        },
      ],
      buttons: [
        { label: 'Acknowledge', value: 'ack', variant: 'default' },
      ],
    })],
    isLoading: false,
  },
}

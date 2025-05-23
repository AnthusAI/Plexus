import React, { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import ItemDetail from '../components/ItemDetail'
import { formatDistanceToNow, parseISO } from 'date-fns'

// Get the current date and time
const now = new Date();

// Function to create a date relative to now
const relativeDate = (days: number, hours: number, minutes: number) => {
  const date = new Date(now);
  date.setDate(date.getDate() - days);
  date.setHours(date.getHours() - hours, date.getMinutes() - minutes);
  return date.toISOString();
};

// Sample metadata for the story
const sampleMetadata = [
  { key: 'Item ID', value: '40000001' },
  { key: 'Account', value: 'Acme Corp' },
  { key: 'Created', value: '2023-10-15T14:30:00Z' },
  { key: 'Duration', value: '5m 23s' },
  { key: 'Agent', value: 'John Smith' },
  { key: 'Customer', value: 'Jane Doe' },
  { key: 'Channel', value: 'Phone' },
  { key: 'Language', value: 'English' },
  { key: 'Region', value: 'North America' },
];

// Sample transcript for the story
const sampleTranscript = [
  { speaker: 'Agent', text: 'Thank you for calling Acme Corp. My name is John. How can I help you today?' },
  { speaker: 'Customer', text: 'Hi John, I\'m calling about my recent order. It hasn\'t arrived yet and it\'s been over a week.' },
  { speaker: 'Agent', text: 'I\'m sorry to hear that. Let me look up your order. Can I have your order number or the email address associated with your account?' },
  { speaker: 'Customer', text: 'Sure, my email is jane.doe@example.com.' },
  { speaker: 'Agent', text: 'Thank you. Let me check that for you... I see your order #12345 was shipped on October 10th and should have been delivered by October 13th. I\'ll check with our shipping department to see what\'s happening.' },
  { speaker: 'Customer', text: 'That would be great, thank you.' },
  { speaker: 'Agent', text: 'I\'ve just checked with shipping and it looks like there was a delay due to weather conditions. The package is now scheduled for delivery tomorrow. Would you like me to send you the tracking information?' },
  { speaker: 'Customer', text: 'Yes, please send it to my email.' },
  { speaker: 'Agent', text: 'I\'ve just sent that to you. Is there anything else I can help you with today?' },
  { speaker: 'Customer', text: 'No, that\'s all. Thank you for your help.' },
  { speaker: 'Agent', text: 'You\'re welcome. Thank you for choosing Acme Corp. Have a great day!' },
];

// Sample score results for the story
const sampleScoreResults = [
  {
    section: 'Customer Experience',
    scores: [
      {
        name: 'Greeting',
        value: 'Yes',
        explanation: 'Agent provided a proper greeting with name and company.',
        isAnnotated: false,
        allowFeedback: true,
        annotations: []
      },
      {
        name: 'Problem Resolution',
        value: 'Yes',
        explanation: 'Agent successfully resolved the customer\'s issue by providing tracking information and delivery update.',
        isAnnotated: true,
        allowFeedback: true,
        annotations: [
          {
            value: 'Yes',
            explanation: 'Agent went above and beyond by checking with shipping department in real-time.',
            annotation: 'Great job following up with shipping department immediately rather than making the customer wait.',
            timestamp: relativeDate(0, 2, 0),
            user: {
              name: 'Supervisor',
              initials: 'SV'
            },
            isThumbsUp: true
          }
        ]
      },
      {
        name: 'Closing',
        value: 'Yes',
        explanation: 'Agent properly closed the call with a thank you and well wishes.',
        isAnnotated: false,
        allowFeedback: true,
        annotations: []
      }
    ]
  },
  {
    section: 'Technical Skills',
    scores: [
      {
        name: 'System Knowledge',
        value: '90%',
        explanation: 'Agent demonstrated good knowledge of the order tracking system and was able to quickly retrieve order information.',
        isAnnotated: false,
        allowFeedback: true,
        annotations: []
      },
      {
        name: 'Process Adherence',
        value: 'Yes',
        explanation: 'Agent followed all required processes for order lookup and issue resolution.',
        isAnnotated: false,
        allowFeedback: true,
        annotations: []
      }
    ]
  },
  {
    section: 'Communication',
    scores: [
      {
        name: 'Clarity',
        value: 'Yes',
        explanation: 'Agent communicated clearly throughout the call.',
        isAnnotated: false,
        allowFeedback: true,
        annotations: []
      },
      {
        name: 'Empathy',
        value: 'No',
        explanation: 'Agent could have shown more empathy when customer mentioned the delayed order.',
        isAnnotated: true,
        allowFeedback: true,
        annotations: [
          {
            value: 'No',
            explanation: 'Agent should have acknowledged customer frustration more explicitly.',
            annotation: 'While the agent did say "I\'m sorry to hear that," they could have acknowledged the inconvenience more specifically.',
            timestamp: relativeDate(0, 1, 30),
            user: {
              name: 'Quality Analyst',
              initials: 'QA'
            },
            isThumbsUp: false
          }
        ]
      }
    ]
  }
];

// Create a wrapper component to manage state
const ItemDetailWrapper = (args: any) => {
  const [isMetadataExpanded, setIsMetadataExpanded] = useState(false);
  const [isDataExpanded, setIsDataExpanded] = useState(false);
  const [isErrorExpanded, setIsErrorExpanded] = useState(false);
  const [expandedAnnotations, setExpandedAnnotations] = useState<string[]>([]);
  const [thumbedUpScores, setThumbedUpScores] = useState<Set<string>>(new Set());
  const [showNewAnnotationForm, setShowNewAnnotationForm] = useState<{ scoreName: string | null; isThumbsUp: boolean }>({ scoreName: null, isThumbsUp: false });
  const [newAnnotation, setNewAnnotation] = useState({ value: '', explanation: '', annotation: '' });
  const [isFullWidth, setIsFullWidth] = useState(false);

  const getBadgeVariant = (status: string) => {
    switch (status) {
      case 'New':
      case 'Scoring':
        return 'bg-neutral text-primary-foreground h-6';
      case 'Done':
        return 'bg-true text-primary-foreground h-6';
      case 'Error':
        return 'bg-destructive text-destructive-foreground dark:text-primary-foreground h-6';
      default:
        return 'bg-muted text-muted-foreground h-6';
    }
  };

  const getRelativeTime = (dateString: string | undefined) => {
    if (!dateString) return '';
    try {
      return formatDistanceToNow(parseISO(dateString), { addSuffix: true });
    } catch (e) {
      return dateString;
    }
  };

  const handleThumbsUp = (scoreName: string) => {
    const newThumbedUpScores = new Set(thumbedUpScores);
    if (newThumbedUpScores.has(scoreName)) {
      newThumbedUpScores.delete(scoreName);
    } else {
      newThumbedUpScores.add(scoreName);
    }
    setThumbedUpScores(newThumbedUpScores);
    setShowNewAnnotationForm({ scoreName, isThumbsUp: true });
  };

  const handleThumbsDown = (scoreName: string) => {
    const newThumbedUpScores = new Set(thumbedUpScores);
    newThumbedUpScores.delete(scoreName);
    setThumbedUpScores(newThumbedUpScores);
    setShowNewAnnotationForm({ scoreName, isThumbsUp: false });
  };

  const handleNewAnnotationSubmit = (scoreName: string) => {
    console.log('New annotation submitted for', scoreName, newAnnotation);
    setShowNewAnnotationForm({ scoreName: null, isThumbsUp: false });
    setNewAnnotation({ value: '', explanation: '', annotation: '' });
  };

  const toggleAnnotations = (scoreName: string) => {
    setExpandedAnnotations(prev => 
      prev.includes(scoreName) 
        ? prev.filter(name => name !== scoreName)
        : [...prev, scoreName]
    );
  };

  return (
    <div className="h-[800px] w-full max-w-[1000px]">
      <ItemDetail
        {...args}
        isMetadataExpanded={isMetadataExpanded}
        setIsMetadataExpanded={setIsMetadataExpanded}
        isDataExpanded={isDataExpanded}
        setIsDataExpanded={setIsDataExpanded}
        isErrorExpanded={isErrorExpanded}
        setIsErrorExpanded={setIsErrorExpanded}
        sampleMetadata={sampleMetadata}
        sampleTranscript={sampleTranscript}
        sampleScoreResults={sampleScoreResults}
        handleThumbsUp={handleThumbsUp}
        handleThumbsDown={handleThumbsDown}
        handleNewAnnotationSubmit={handleNewAnnotationSubmit}
        toggleAnnotations={toggleAnnotations}
        showNewAnnotationForm={showNewAnnotationForm}
        setShowNewAnnotationForm={setShowNewAnnotationForm}
        newAnnotation={newAnnotation}
        setNewAnnotation={setNewAnnotation}
        expandedAnnotations={expandedAnnotations}
        thumbedUpScores={thumbedUpScores}
        setThumbedUpScores={setThumbedUpScores}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        getBadgeVariant={getBadgeVariant}
        getRelativeTime={getRelativeTime}
      />
    </div>
  );
};

const meta = {
  title: 'Scorecards/ItemDetail',
  component: ItemDetailWrapper,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ItemDetailWrapper>;

export default meta;
type Story = StoryObj<typeof meta>;

// Create the default story
export const Default: Story = {
  args: {
    item: {
      scorecard: 'Customer Service Evaluation',
      inferences: '24',
      results: '7',
      cost: '$0.031',
      status: 'Done',
      date: relativeDate(0, 2, 0),
      sampleMetadata: sampleMetadata,
      sampleTranscript: sampleTranscript,
      sampleScoreResults: sampleScoreResults,
    },
    isFeedbackMode: true,
    onClose: () => console.log('Close clicked'),
  },
};

// Create a story for an item with error status
export const WithError: Story = {
  args: {
    item: {
      scorecard: 'Customer Service Evaluation',
      inferences: '4',
      results: '2',
      cost: '$0.005',
      status: 'Error',
      date: relativeDate(0, 1, 0),
      sampleMetadata: sampleMetadata,
      sampleTranscript: sampleTranscript,
      sampleScoreResults: sampleScoreResults,
    },
    isFeedbackMode: true,
    onClose: () => console.log('Close clicked'),
  },
};

// Create a story for a new item
export const NewItem: Story = {
  args: {
    item: {
      scorecard: 'Customer Service Evaluation',
      inferences: '0',
      results: '0',
      cost: '$0.000',
      status: 'New',
      date: relativeDate(0, 0, 15),
      sampleMetadata: sampleMetadata,
      sampleTranscript: sampleTranscript,
      sampleScoreResults: sampleScoreResults,
    },
    isFeedbackMode: false,
    onClose: () => console.log('Close clicked'),
  },
}; 
import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { FeedbackItemsView, type FeedbackItem } from '@/components/ui/feedback-item-view';

const meta: Meta<typeof FeedbackItemsView> = {
  title: 'Reports/Components/FeedbackItemsView',
  component: FeedbackItemsView,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-4xl mx-auto">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof FeedbackItemsView>;

// Sample feedback items for stories
const agreementItem: FeedbackItem = {
  id: '8940c751-b887-41a1-b120-fa7d3c9b583d',
  initialAnswerValue: 'Yes',
  finalAnswerValue: 'Yes',
  initialCommentValue: 'The agent confirmed the patient\'s pharmacy information during the conversation. The patient stated that they use Walgreens, and the agent acknowledged this and discussed the transition to a new pharmacy service. Quotation: "Customer: Yeah. Walgreens."',
  finalCommentValue: '',
  editCommentValue: 'No changes needed, the initial assessment was correct.',
  isAgreement: true,
  scorecardId: '59125ba2-670c-4aa5-b796-c2085cf38a0c',
  scoreId: '3ec637a1-5c59-4314-a757-670a0e7a9e76',
  cacheKey: '3ec637a1-5c59-4314-a757-670a0e7a9e76:56057980',
  createdAt: '2025-05-19 19:40:10.161000+00:00',
  updatedAt: '2025-05-19 19:40:58.062000+00:00'
};

const disagreementItem: FeedbackItem = {
  id: '7830d642-a997-31b1-c130-eb8c3c9b473e',
  initialAnswerValue: 'No',
  finalAnswerValue: 'Yes',
  initialCommentValue: 'The agent did not verify the pharmacy information.',
  finalCommentValue: 'Upon review, the agent did verify the pharmacy as Walgreens at timestamp 2:35.',
  editCommentValue: 'Changed from No to Yes after listening to the call recording more carefully.',
  isAgreement: false,
  scorecardId: '59125ba2-670c-4aa5-b796-c2085cf38a0c',
  scoreId: '3ec637a1-5c59-4314-a757-670a0e7a9e76',
  createdAt: '2025-05-19 18:30:10.161000+00:00',
  updatedAt: '2025-05-19 18:45:58.062000+00:00'
};

const partialDisagreementItem: FeedbackItem = {
  id: '6732b531-f765-42e1-a123-de7f8c2b492f',
  initialAnswerValue: 'Partially',
  finalAnswerValue: 'Yes',
  initialCommentValue: 'The agent asked about the pharmacy but did not confirm the information.',
  finalCommentValue: 'The agent did confirm the pharmacy information adequately.',
  editCommentValue: 'Updated after review of conversation transcript.',
  isAgreement: false,
  scorecardId: '59125ba2-670c-4aa5-b796-c2085cf38a0c',
  scoreId: '3ec637a1-5c59-4314-a757-670a0e7a9e76',
  createdAt: '2025-05-19 17:15:10.161000+00:00',
  updatedAt: '2025-05-19 17:30:58.062000+00:00'
};

const noCommentsItem: FeedbackItem = {
  id: '5621d742-c886-33a1-b120-fa7d3c9b584f',
  initialAnswerValue: 'Yes',
  finalAnswerValue: 'No',
  initialCommentValue: '',
  finalCommentValue: '',
  editCommentValue: '',
  isAgreement: false,
  scorecardId: '59125ba2-670c-4aa5-b796-c2085cf38a0c',
  scoreId: '3ec637a1-5c59-4314-a757-670a0e7a9e76',
  createdAt: '2025-05-19 16:00:10.161000+00:00',
  updatedAt: '2025-05-19 16:15:58.062000+00:00'
};

const mixedItems: FeedbackItem[] = [
  agreementItem,
  disagreementItem,
  partialDisagreementItem,
  noCommentsItem,
  {
    ...agreementItem,
    id: 'duplicate-1',
    initialCommentValue: 'Another agreement case with different commentary.',
    finalCommentValue: 'Confirmed upon review.',
    editCommentValue: 'No changes needed.'
  }
];

// Interactive wrapper component for toggle functionality
const InteractiveFeedbackItemsView = (args: any) => {
  const [showRawJson, setShowRawJson] = useState(args.initialShowRawJson || false);
  
  return (
    <FeedbackItemsView 
      {...args}
      showRawJson={showRawJson}
      onToggleView={() => setShowRawJson(!showRawJson)}
    />
  );
};

export const ConfusionMatrixDrillDown: Story = {
  render: (args) => <InteractiveFeedbackItemsView {...args} />,
  args: {
    items: mixedItems,
    filterInfo: {
      predicted: 'Yes',
      actual: 'Yes',
      count: 5
    },
    onClose: () => console.log('Close button clicked'),
    initialShowRawJson: false
  },
};

export const DisagreementCases: Story = {
  render: (args) => <InteractiveFeedbackItemsView {...args} />,
  args: {
    items: [disagreementItem, partialDisagreementItem, noCommentsItem],
    filterInfo: {
      predicted: 'Yes',
      actual: 'No',
      count: 3
    },
    onClose: () => console.log('Close button clicked'),
    initialShowRawJson: false
  },
};

export const AgreementCases: Story = {
  render: (args) => <InteractiveFeedbackItemsView {...args} />,
  args: {
    items: [agreementItem, {
      ...agreementItem,
      id: 'agreement-2',
      initialCommentValue: 'Clear confirmation of patient understanding.',
      editCommentValue: 'Assessment was accurate.'
    }],
    filterInfo: {
      predicted: 'Yes',
      actual: 'Yes', 
      count: 2
    },
    onClose: () => console.log('Close button clicked'),
    initialShowRawJson: false
  },
};

export const RawJsonView: Story = {
  render: (args) => <InteractiveFeedbackItemsView {...args} />,
  args: {
    items: mixedItems,
    filterInfo: {
      predicted: 'Yes',
      actual: 'No',
      count: 5
    },
    onClose: () => console.log('Close button clicked'),
    initialShowRawJson: true
  },
};

export const LoadingState: Story = {
  render: (args) => <InteractiveFeedbackItemsView {...args} />,
  args: {
    items: [],
    isLoading: true,
    filterInfo: {
      predicted: 'Yes',
      actual: 'No',
      count: 0
    },
    onClose: () => console.log('Close button clicked')
  },
};

export const EmptyResults: Story = {
  render: (args) => <InteractiveFeedbackItemsView {...args} />,
  args: {
    items: [],
    isLoading: false,
    filterInfo: {
      predicted: 'Maybe',
      actual: 'Definitely',
      count: 0
    },
    onClose: () => console.log('Close button clicked')
  },
};

export const SingleItem: Story = {
  render: (args) => <InteractiveFeedbackItemsView {...args} />,
  args: {
    items: [disagreementItem],
    filterInfo: {
      predicted: 'No',
      actual: 'Yes',
      count: 1
    },
    onClose: () => console.log('Close button clicked'),
    initialShowRawJson: false
  },
};

export const NoFilterInfo: Story = {
  render: (args) => <InteractiveFeedbackItemsView {...args} />,
  args: {
    items: mixedItems,
    onClose: () => console.log('Close button clicked'),
    initialShowRawJson: false
  },
};
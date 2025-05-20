import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { FeedbackItemView, FeedbackItemsList, FeedbackItemsView, type FeedbackItem } from '@/components/ui/feedback-item-view';

const meta: Meta<typeof FeedbackItemView> = {
  title: 'UI/FeedbackItemView',
  component: FeedbackItemView,
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof FeedbackItemView>;

const sampleItem: FeedbackItem = {
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

const listItems: FeedbackItem[] = [
  sampleItem,
  disagreementItem,
  {
    ...sampleItem,
    id: '6732b531-f765-42e1-a123-de7f8c2b492f',
    initialAnswerValue: 'Partially',
    finalAnswerValue: 'Yes',
    initialCommentValue: 'The agent asked about the pharmacy but did not confirm the information.',
    finalCommentValue: 'The agent did confirm the pharmacy information adequately.',
    editCommentValue: 'Updated after review of conversation transcript.',
    isAgreement: false,
  },
];

export const Default: Story = {
  args: {
    item: sampleItem
  },
};

export const Disagreement: Story = {
  args: {
    item: disagreementItem
  },
};

export const NoComments: Story = {
  args: {
    item: {
      ...sampleItem,
      initialCommentValue: '',
      finalCommentValue: '',
      editCommentValue: '',
    }
  },
};

// Story for the FeedbackItemsList component
export const ItemsList: StoryObj<typeof FeedbackItemsList> = {
  render: (args) => <FeedbackItemsList {...args} />,
  args: {
    items: listItems
  },
};

// Stories for the FeedbackItemsView component with toggle functionality
export const ItemsViewWithRawJson: StoryObj<typeof FeedbackItemsView> = {
  render: (args) => {
    const [showRawJson, setShowRawJson] = useState(true);
    return (
      <FeedbackItemsView 
        {...args}
        showRawJson={showRawJson}
        onToggleView={() => setShowRawJson(!showRawJson)}
      />
    );
  },
  args: {
    items: listItems,
    filterInfo: {
      predicted: 'Yes',
      actual: 'Yes',
      count: 3
    },
    onClose: () => console.log('Close button clicked')
  },
};

export const ItemsViewWithListView: StoryObj<typeof FeedbackItemsView> = {
  render: (args) => {
    const [showRawJson, setShowRawJson] = useState(false);
    return (
      <FeedbackItemsView 
        {...args}
        showRawJson={showRawJson}
        onToggleView={() => setShowRawJson(!showRawJson)}
      />
    );
  },
  args: {
    items: listItems,
    filterInfo: {
      predicted: 'Yes',
      actual: 'No',
      count: 3
    },
    onClose: () => console.log('Close button clicked')
  },
};

export const ItemsViewLoading: StoryObj<typeof FeedbackItemsView> = {
  render: (args) => {
    const [showRawJson, setShowRawJson] = useState(false);
    return (
      <FeedbackItemsView 
        {...args}
        showRawJson={showRawJson}
        onToggleView={() => setShowRawJson(!showRawJson)}
      />
    );
  },
  args: {
    items: [],
    isLoading: true
  },
}; 
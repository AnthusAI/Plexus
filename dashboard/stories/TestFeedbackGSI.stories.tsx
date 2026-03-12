import type { Meta, StoryObj } from '@storybook/react';
import { TestFeedbackGSI } from '@/components/test-feedback-gsi';

const meta: Meta<typeof TestFeedbackGSI> = {
  title: 'Test/Feedback GSI',
  component: TestFeedbackGSI,
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof TestFeedbackGSI>;

export const Default: Story = {};
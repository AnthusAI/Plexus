import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import NivoWaffle, { NivoWaffleProps } from './NivoWaffle';

export default {
  title: 'VisualizationNivoWaffle',
  component: NivoWaffle,
} as Meta<typeof NivoWaffle>;

const Template: StoryFn<NivoWaffleProps> = (args) => <NivoWaffle {...args} />;

export const Default = Template.bind({});
Default.args = {
  processedItems: 75,
  totalItems: 100,
  accuracy: 80,
};

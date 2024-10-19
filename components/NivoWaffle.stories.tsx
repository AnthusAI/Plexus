import React from 'react';
import { Story, Meta } from '@storybook/react';
import NivoWaffle, { NivoWaffleProps } from './NivoWaffle';

export default {
  title: 'Components/NivoWaffle',
  component: NivoWaffle,
} as Meta;

const Template: Story<NivoWaffleProps> = (args) => <NivoWaffle {...args} />;

export const Default = Template.bind({});
Default.args = {
  processedItems: 75,
  totalItems: 100,
  accuracy: 80,
};

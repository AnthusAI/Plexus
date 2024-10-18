import React from 'react';
import { Preview } from '@storybook/react';
import '../app/globals.css';

const preview: Preview = {
  parameters: {
    layout: 'fullscreen',
    actions: { argTypesRegex: "^on[A-Z].*" },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/,
      },
    },
  },
  decorators: [
    (Story) => (
      <div className="p-4 bg-background">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Story />
        </div>
      </div>
    ),
  ],
};

export default preview;

import React from 'react';
import type { Preview } from "@storybook/react";
import '../app/globals.css';
import { ThemeProvider } from '@/components/theme-provider';
import { withThemeByClassName } from "@storybook/addon-themes";

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
    darkMode: {
      dark: ["class", '[data-mode="dark"]'],
    },
  },
  decorators: [
    withThemeByClassName({ 
      themes: { light: "light", dark: "dark" }, 
      defaultTheme: "light" 
    }),
    (Story) => (
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <div className="p-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <Story />
          </div>
        </div>
      </ThemeProvider>
    ),
  ],
};

export default preview;

import React from 'react';
import type { Preview } from "@storybook/react";
import '../app/globals.css';
import { ThemeProvider } from '../components/theme-provider';
import { withThemeByClassName } from "@storybook/addon-themes";

const mockNextNavigation = (Story: React.ComponentType) => {
  // @ts-ignore - we're mocking the router
  window.next = {
    router: {
      push: async () => {},
      back: () => {},
      forward: () => {},
      refresh: () => {},
      replace: () => {},
      prefetch: () => {}
    }
  };

  return <Story />;
};

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
    mockNextNavigation,
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
        <div className="min-h-screen bg-background p-4">
          <Story />
        </div>
      </ThemeProvider>
    ),
  ],
};

export default preview;

import React from 'react';
import type { Preview } from "@storybook/react";
import '../app/globals.css';
import { ThemeProvider } from '../components/theme-provider';
import { withThemeByClassName } from "@storybook/addon-themes";

const mockNextNavigation = (Story: React.ComponentType) => {
  // Mock the Next.js app router
  // @ts-ignore - we're mocking the router
  window.next = {
    router: {
      back: () => {},
      forward: () => {},
      refresh: () => {},
      push: async () => {},
      replace: async () => {},
      prefetch: async () => {},
      beforePopState: () => {},
      events: {
        on: () => {},
        off: () => {},
        emit: () => {},
      },
      isFallback: false,
      isLocaleDomain: false,
      isPreview: false,
      isReady: true,
      route: '/',
      basePath: '',
      pathname: '/',
      query: {},
      asPath: '/',
      locale: undefined,
      locales: undefined,
      defaultLocale: undefined,
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
    nextjs: {
      appDirectory: true,
      navigation: {
        pathname: '/',
        query: {},
      },
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

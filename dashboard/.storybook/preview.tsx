import React from 'react';
import type { Preview } from "@storybook/react";
import '../app/globals.css';
import { ThemeProvider } from '../components/theme-provider';
import { withThemeByClassName } from "@storybook/addon-themes";
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

// Import the block registry setup for side effects (registers blocks globally for Storybook)
import "@/components/blocks/registrySetup";

// Mock Amplify generateClient for Storybook
const mockGenerateClient = () => ({
  models: {
    Account: {
      list: async () => ({
        data: [
          {
            id: 'mock-account-1',
            key: 'call-criteria',
            name: 'Mock Account',
            settings: null,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          }
        ]
      })
    }
  }
});

// Mock the generateClient function globally for Storybook
(global as any).generateClient = mockGenerateClient;

// Mock AWS Amplify configuration for Storybook
const mockAmplifyConfig = {
  Auth: {
    Cognito: {
      userPoolId: 'mock-user-pool',
      userPoolClientId: 'mock-client-id',
      region: 'us-east-1',
    }
  }
};

// Configure Amplify with mock config for Storybook
if (typeof window !== 'undefined') {
  try {
    const { Amplify } = require('aws-amplify');
    Amplify.configure(mockAmplifyConfig);
  } catch (error) {
    console.warn('Could not configure Amplify for Storybook:', error);
  }
}

// Mock useAuthenticator hook for Storybook
const mockUseAuthenticator = (selector?: any) => {
  const mockAuthState = {
    authStatus: 'authenticated',
    user: {
      username: 'mock-user',
      attributes: {
        email: 'mock@example.com'
      }
    }
  };
  
  // If a selector is provided, return the selected parts
  if (typeof selector === 'function') {
    return selector(mockAuthState);
  }
  
  // Otherwise return the full mock state
  return mockAuthState;
};

// Replace useAuthenticator globally for Storybook
if (typeof window !== 'undefined') {
  try {
    const amplifyUiReact = require('@aws-amplify/ui-react');
    amplifyUiReact.useAuthenticator = mockUseAuthenticator;
  } catch (error) {
    console.warn('Could not mock useAuthenticator for Storybook:', error);
  }
}

// Create a robust mock AccountProvider and useAccount hook for Storybook
const mockAccount = {
  id: 'mock-account-1',
  key: 'call-criteria',
  name: 'Mock Account',
  settings: null,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

const mockAccountContext = {
  accounts: [mockAccount],
  selectedAccount: mockAccount,
  isLoadingAccounts: false,
  visibleMenuItems: [],
  setSelectedAccount: () => {},
  refreshAccount: async () => {},
  refetchAccounts: async () => {},
};

// Create the AccountContext
const MockAccountContext = React.createContext(mockAccountContext);

// Mock useAccount hook
const mockUseAccount = () => {
  const context = React.useContext(MockAccountContext);
  if (context === undefined) {
    // For testing, always return the mock context
    return mockAccountContext;
  }
  return context;
};

// Mock AccountProvider for Storybook
const MockAccountProvider = ({ children }: { children: React.ReactNode }) => {
  return (
    <MockAccountContext.Provider value={mockAccountContext}>
      {children}
    </MockAccountContext.Provider>
  );
};

// Install the mock useAccount hook globally
if (typeof window !== 'undefined') {
  // Override the useAccount hook globally for components that import it
  (global as any).useAccount = mockUseAccount;
  (window as any).useAccount = mockUseAccount;
  
  // Monkey patch the require/import system to return our mock
  const originalImport = (global as any).__import || ((global as any).import);
  if (originalImport) {
    (global as any).__import = (global as any).import = async function(module: string) {
      if (module.includes('AccountContext')) {
        return {
          useAccount: mockUseAccount,
          AccountProvider: MockAccountProvider,
        };
      }
      return originalImport.apply(this, arguments);
    };
  }
}

// Add Google Font
const GoogleFontDecorator = (Story: React.ComponentType) => {
  React.useEffect(() => {
    const link = document.createElement('link');
    link.href = 'https://fonts.googleapis.com/css2?family=Jersey+20&display=swap';
    link.rel = 'stylesheet';
    document.head.appendChild(link);
    return () => {
      document.head.removeChild(link);
    };
  }, []);
  return <Story />;
};

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
    options: {
      storySort: {
        order: [
          'Theme', ['Logo', 'ColorPalette', '*'],
          'Landing Pages',
          'General',
          'Evaluations',
          'Reports',
          'Scorecards',
          '*'
        ],
      },
    },
  },
  decorators: [
    GoogleFontDecorator,
    mockNextNavigation,
    withThemeByClassName({ 
      themes: { light: "light", dark: "dark" }, 
      defaultTheme: "light" 
    }),
    (Story) => (
      <Authenticator.Provider>
        <MockAccountProvider>
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
        </MockAccountProvider>
      </Authenticator.Provider>
    ),
  ],
};

export default preview;
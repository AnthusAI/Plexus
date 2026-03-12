// Global mocks for Storybook

// Mock account data
export const mockAccount = {
  id: 'mock-account-1',
  key: 'call-criteria',
  name: 'Mock Account',
  settings: null,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

export const mockAccountContext = {
  accounts: [mockAccount],
  selectedAccount: mockAccount,
  isLoadingAccounts: false,
  visibleMenuItems: [],
  setSelectedAccount: () => {},
  refreshAccount: async () => {},
  refetchAccounts: async () => {},
};

// Mock useAccount hook
export const useAccount = () => mockAccountContext;

// Mock AccountProvider
export const AccountProvider = ({ children }: { children: React.ReactNode }) => {
  return <>{children}</>;
};

// Set up global mocks
if (typeof window !== 'undefined') {
  // Override ES module imports
  const originalImport = window.eval('import');
  if (originalImport) {
    window.eval('import') = async function(module: string) {
      if (module.includes('AccountContext')) {
        return {
          useAccount,
          AccountProvider,
        };
      }
      return originalImport.apply(this, arguments);
    };
  }
  
  // Override require calls
  const Module = require('module');
  const originalRequire = Module.prototype.require;
  Module.prototype.require = function(id: string) {
    if (id.includes('AccountContext')) {
      return {
        useAccount,
        AccountProvider,
      };
    }
    return originalRequire.apply(this, arguments);
  };
}

import React from 'react';

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

export const useAccount = () => mockAccountContext;

export const AccountProvider = ({ children }: { children: React.ReactNode }) => {
  return React.createElement(React.Fragment, null, children);
};

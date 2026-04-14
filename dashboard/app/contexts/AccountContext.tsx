"use client"

import React, { createContext, useContext, useEffect, useState } from 'react'
import { useAuthenticator } from '@aws-amplify/ui-react'
import type { Schema } from "@/amplify/data/resource"
import type { AccountSettings } from "@/types/account-config"
import { isValidAccountSettings } from "@/types/account-config"
import { listFromModel } from "@/utils/amplify-helpers"
import { getClient } from "@/utils/amplify-client"
import { menuItems } from "@/components/dashboard-layout"

type Account = Schema['Account']['type']
const LAST_ACCOUNT_STORAGE_KEY = "plexus.lastSelectedAccountId"

interface AccountContextType {
  accounts: Account[]
  selectedAccount: Account | null
  isLoadingAccounts: boolean
  visibleMenuItems: { name: string; icon: any; path: string }[]
  setSelectedAccount: (account: Account) => void
  refreshAccount: () => Promise<void>
  refetchAccounts: () => Promise<void>
}

const AccountContext = createContext<AccountContextType | undefined>(undefined)

export function AccountProvider({ children }: { children: React.ReactNode }) {
  const { authStatus } = useAuthenticator(context => [context.authStatus])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selectedAccount, setSelectedAccountState] = useState<Account | null>(null)
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(true)
  const [visibleMenuItems, setVisibleMenuItems] = useState<typeof menuItems>(menuItems)

  const readStoredAccountId = (): string | null => {
    if (typeof window === 'undefined') return null
    const stored = window.localStorage.getItem(LAST_ACCOUNT_STORAGE_KEY)
    return stored?.trim() || null
  }

  const writeStoredAccountId = (accountId: string | null) => {
    if (typeof window === 'undefined') return
    if (accountId) {
      window.localStorage.setItem(LAST_ACCOUNT_STORAGE_KEY, accountId)
      return
    }
    window.localStorage.removeItem(LAST_ACCOUNT_STORAGE_KEY)
  }

  const updateVisibleMenuItems = (account: Account | null) => {
    if (account?.settings) {
      const settings = typeof account.settings === 'string' ? 
        JSON.parse(account.settings) : account.settings
      if (isValidAccountSettings(settings)) {
        setVisibleMenuItems(menuItems.filter(item => 
          !settings.hiddenMenuItems.includes(item.name)
        ))
      } else {
        setVisibleMenuItems(menuItems)
      }
    } else {
      setVisibleMenuItems(menuItems)
    }
  }

  const applySelectedAccount = (account: Account | null) => {
    setSelectedAccountState(account)
    writeStoredAccountId(account?.id ?? null)
    updateVisibleMenuItems(account)
  }

  const selectPreferredAccount = (availableAccounts: Account[]): Account | null => {
    if (availableAccounts.length === 0) return null

    const storedAccountId = readStoredAccountId()
    if (storedAccountId) {
      const storedAccount = availableAccounts.find(account => account.id === storedAccountId)
      if (storedAccount) return storedAccount
    }

    const defaultAccountKey = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY?.trim()
    if (defaultAccountKey) {
      const envAccount = availableAccounts.find(account => account.key === defaultAccountKey)
      if (envAccount) return envAccount
    }

    return availableAccounts[0]
  }

  const refreshAccount = async () => {
    if (!selectedAccount) return
    try {
      const client = getClient()
      const { data: accountsData } = await listFromModel<Schema['Account']['type']>(
        client.models.Account
      )
      const updatedAccount = accountsData.find(a => a.id === selectedAccount.id)
      if (updatedAccount) {
        applySelectedAccount(updatedAccount)
      }
    } catch (error) {
      console.error('Error refreshing account:', error)
    }
  }

  const refetchAccounts = async () => {
    if (authStatus !== 'authenticated') {
      return
    }

    setIsLoadingAccounts(true)
    try {
      const client = getClient()
      const { data: accountsData } = await listFromModel<Schema['Account']['type']>(
        client.models.Account
      )
      
      const accountsWithParsedSettings = accountsData.map(account => ({
        ...account,
        settings: typeof account.settings === 'string' ? 
          JSON.parse(account.settings) : account.settings
      }))
      
      setAccounts(accountsWithParsedSettings)
      
      // Reset selected account if it's no longer in the list
      if (selectedAccount && !accountsWithParsedSettings.find(a => a.id === selectedAccount.id)) {
        const defaultAccount = selectPreferredAccount(accountsWithParsedSettings)
        
        if (defaultAccount) {
          applySelectedAccount(defaultAccount)
        } else {
          applySelectedAccount(null)
        }
      }
    } catch (error) {
      console.error('Error refetching accounts:', error)
    } finally {
      setIsLoadingAccounts(false)
    }
  }

  // Clear account state when user logs out
  useEffect(() => {
    if (authStatus === 'unauthenticated') {
      setAccounts([])
      setSelectedAccountState(null)
      setVisibleMenuItems(menuItems)
      setIsLoadingAccounts(false)
    }
  }, [authStatus])

  useEffect(() => {
    async function fetchAccounts() {
      // While auth is initializing, keep loading true to avoid transient
      // "no account" states in downstream dashboards.
      if (authStatus === 'configuring') {
        return
      }

      // Only fetch accounts if user is authenticated
      if (authStatus !== 'authenticated') {
        setIsLoadingAccounts(false)
        return
      }

      setIsLoadingAccounts(true)
      try {
        const client = getClient()
        const { data: accountsData } = await listFromModel<Schema['Account']['type']>(
          client.models.Account
        )
        
        const accountsWithParsedSettings = accountsData.map(account => ({
          ...account,
          settings: typeof account.settings === 'string' ? 
            JSON.parse(account.settings) : account.settings
        }))
        
        setAccounts(accountsWithParsedSettings)
        
        // Set default account if none is selected
        if (!selectedAccount && accountsWithParsedSettings.length > 0) {
          const defaultAccount = selectPreferredAccount(accountsWithParsedSettings)
          
          if (defaultAccount) {
            applySelectedAccount(defaultAccount)
          }
        }
      } catch (error) {
        console.error('Error fetching accounts:', error)
      } finally {
        setIsLoadingAccounts(false)
      }
    }

    fetchAccounts()
  }, [authStatus, selectedAccount])

  useEffect(() => {
    updateVisibleMenuItems(selectedAccount)
  }, [selectedAccount])

  return (
    <AccountContext.Provider value={{
      accounts,
      selectedAccount,
      isLoadingAccounts,
      visibleMenuItems,
      setSelectedAccount: (account: Account) => applySelectedAccount(account),
      refreshAccount,
      refetchAccounts
    }}>
      {children}
    </AccountContext.Provider>
  )
}

export function useAccount() {
  const context = useContext(AccountContext)
  if (context === undefined) {
    throw new Error('useAccount must be used within an AccountProvider')
  }
  return context
} 

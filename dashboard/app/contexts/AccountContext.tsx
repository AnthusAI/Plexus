"use client"

import React, { createContext, useContext, useEffect, useState } from 'react'
import { generateClient } from "aws-amplify/api"
import { useAuthenticator } from '@aws-amplify/ui-react'
import type { Schema } from "@/amplify/data/resource"
import type { AccountSettings } from "@/types/account-config"
import { isValidAccountSettings } from "@/types/account-config"
import { listFromModel } from "@/utils/amplify-helpers"
import { menuItems } from "@/components/dashboard-layout"

const client = generateClient<Schema>()

type Account = Schema['Account']['type']

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
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null)
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(true)
  const [visibleMenuItems, setVisibleMenuItems] = useState<typeof menuItems>(menuItems)

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

  const refreshAccount = async () => {
    if (!selectedAccount) return
    try {
      const { data: accountsData } = await listFromModel<Schema['Account']['type']>(
        client.models.Account
      )
      const updatedAccount = accountsData.find(a => a.id === selectedAccount.id)
      if (updatedAccount) {
        setSelectedAccount(updatedAccount)
        updateVisibleMenuItems(updatedAccount)
      }
    } catch (error) {
      console.error('Error refreshing account:', error)
    }
  }

  const refetchAccounts = async () => {
    if (authStatus !== 'authenticated') {
      console.log('User not authenticated, cannot refetch accounts')
      return
    }

    setIsLoadingAccounts(true)
    try {
      console.log('Refetching accounts...')
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
        const defaultAccountKey = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY
        const defaultAccount = (defaultAccountKey 
          ? accountsWithParsedSettings.find(account => account.key === defaultAccountKey)
          : null) || accountsWithParsedSettings[0]
        
        if (defaultAccount) {
          setSelectedAccount(defaultAccount)
          updateVisibleMenuItems(defaultAccount)
        } else {
          setSelectedAccount(null)
          setVisibleMenuItems(menuItems)
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
      console.log('User unauthenticated, clearing account state')
      setAccounts([])
      setSelectedAccount(null)
      setVisibleMenuItems(menuItems)
      setIsLoadingAccounts(false)
    }
  }, [authStatus])

  useEffect(() => {
    async function fetchAccounts() {
      // Only fetch accounts if user is authenticated
      if (authStatus !== 'authenticated') {
        console.log('User not authenticated, skipping account fetch. Auth status:', authStatus)
        setIsLoadingAccounts(false)
        return
      }

      try {
        console.log('Fetching accounts for authenticated user...')
        const { data: accountsData } = await listFromModel<Schema['Account']['type']>(
          client.models.Account
        )
        console.log('Raw accounts data:', accountsData)
        
        const accountsWithParsedSettings = accountsData.map(account => ({
          ...account,
          settings: typeof account.settings === 'string' ? 
            JSON.parse(account.settings) : account.settings
        }))
        
        console.log('Processed accounts:', accountsWithParsedSettings)
        setAccounts(accountsWithParsedSettings)
        
        // Set default account if none is selected
        if (!selectedAccount && accountsWithParsedSettings.length > 0) {
          const defaultAccountKey = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY
          const defaultAccount = (defaultAccountKey 
            ? accountsWithParsedSettings.find(account => account.key === defaultAccountKey)
            : null) || accountsWithParsedSettings[0]
          
          console.log('Setting default account:', defaultAccount)
          if (defaultAccount) {
            setSelectedAccount(defaultAccount)
            updateVisibleMenuItems(defaultAccount)
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
      setSelectedAccount,
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
"use client"

import React, { createContext, useContext, useEffect, useState } from 'react'
import { generateClient } from "aws-amplify/api"
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
}

const AccountContext = createContext<AccountContextType | undefined>(undefined)

export function AccountProvider({ children }: { children: React.ReactNode }) {
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

  useEffect(() => {
    async function fetchAccounts() {
      try {
        const { data: accountsData } = await listFromModel<Schema['Account']['type']>(
          client.models.Account
        )
        const accountsWithParsedSettings = accountsData.map(account => ({
          ...account,
          settings: typeof account.settings === 'string' ? 
            JSON.parse(account.settings) : account.settings
        }))
        setAccounts(accountsWithParsedSettings)
        if (accountsWithParsedSettings.length > 0 && !selectedAccount) {
          const firstAccount = accountsWithParsedSettings[0]
          setSelectedAccount(firstAccount)
          updateVisibleMenuItems(firstAccount)
        }
      } catch (error) {
        console.error('Error fetching accounts:', error)
      } finally {
        setIsLoadingAccounts(false)
      }
    }

    fetchAccounts()
  }, [])

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
      refreshAccount
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
"use client"

import React, { useState, useEffect, useCallback, useRef } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ArrowLeft, Save } from "lucide-react"
import { useRouter } from 'next/navigation'
import { getClient } from '@/utils/amplify-client'
import type { GraphQLResult } from '@aws-amplify/api'
import { toast } from "sonner"
import { useAuthenticator } from '@aws-amplify/ui-react'
import Editor, { Monaco } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import type { editor } from 'monaco-editor'
import { parse as parseYaml, stringify as stringifyYaml } from 'yaml'
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions } from '@/lib/monaco-theme'

// Define types based on Amplify schema
type ReportConfiguration = {
  id: string
  name: string
  description?: string | null
  configuration: string
  accountId: string
  createdAt: string
  updatedAt: string
}

// GraphQL query to get a report configuration
const GET_REPORT_CONFIGURATION = `
  query GetReportConfiguration($id: ID!) {
    getReportConfiguration(id: $id) {
      id
      name
      description
      configuration
      accountId
      createdAt
      updatedAt
    }
  }
`

// GraphQL mutation to create a report configuration
const CREATE_REPORT_CONFIGURATION = `
  mutation CreateReportConfiguration($input: CreateReportConfigurationInput!) {
    createReportConfiguration(input: $input) {
      id
      name
      description
      configuration
      accountId
      createdAt
      updatedAt
    }
  }
`

// GraphQL mutation to update a report configuration
const UPDATE_REPORT_CONFIGURATION = `
  mutation UpdateReportConfiguration($input: UpdateReportConfigurationInput!) {
    updateReportConfiguration(input: $input) {
      id
      name
      description
      configuration
      accountId
      createdAt
      updatedAt
    }
  }
`

const ACCOUNT_KEY = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY || 'call-criteria'

const defaultConfiguration = `# Report Configuration

# Add your report blocks here using the following format:
# \`\`\`block name="Block Name"
# class: BlockClassName
# param1: value1
# param2: value2
# \`\`\`
`

export function ReportConfigurationEdit({ id }: { id: string }) {
  const { user } = useAuthenticator()
  const router = useRouter()
  const [configuration, setConfiguration] = useState<ReportConfiguration | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [hasChanges, setHasChanges] = useState(false)
  const monacoRef = useRef<Monaco | null>(null)
  const editorInstanceRef = useRef<editor.IStandaloneCodeEditor | null>(null)

  // Fetch account ID
  useEffect(() => {
    const fetchAccountId = async () => {
      try {
        const accountResponse = await getClient().graphql({
          query: `
            query ListAccounts($filter: ModelAccountFilterInput) {
              listAccounts(filter: $filter) {
                items {
                  id
                  key
                }
              }
            }
          `,
          variables: {
            filter: { key: { eq: ACCOUNT_KEY } }
          }
        })

        if ('data' in accountResponse && accountResponse.data?.listAccounts?.items?.length) {
          const id = accountResponse.data.listAccounts.items[0].id
          setAccountId(id)
        } else {
          console.warn('No account found with key:', ACCOUNT_KEY)
          setError('No account found')
          setIsLoading(false)
        }
      } catch (err: any) {
        console.error('Error fetching account:', err)
        setError(`Error fetching account: ${err.message}`)
        setIsLoading(false)
      }
    }
    fetchAccountId()
  }, [])

  // Fetch report configuration
  useEffect(() => {
    const fetchConfiguration = async () => {
      if (!accountId) return
      if (id === 'new') {
        setConfiguration({
          id: '',
          name: 'New Report Configuration',
          description: '',
          configuration: defaultConfiguration,
          accountId,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        })
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      setError(null)
      try {
        const response = await getClient().graphql<GraphQLResult<{
          getReportConfiguration: ReportConfiguration
        }>>({
          query: GET_REPORT_CONFIGURATION,
          variables: { id }
        })

        if ('data' in response && response.data?.getReportConfiguration) {
          setConfiguration(response.data.getReportConfiguration)
        } else {
          setError('Report configuration not found')
        }
      } catch (err: any) {
        console.error('Error fetching report configuration:', err)
        setError(`Error fetching report configuration: ${err.message}`)
      } finally {
        setIsLoading(false)
      }
    }

    fetchConfiguration()
  }, [id, accountId])

  // Set up Monaco theme watcher
  useEffect(() => {
    if (!monacoRef.current) return
    
    const cleanup = setupMonacoThemeWatcher(monacoRef.current)
    return cleanup
  }, [monacoRef.current])

  const handleSave = async () => {
    if (!configuration || !accountId) return

    try {
      const input = {
        name: configuration.name,
        description: configuration.description,
        configuration: configuration.configuration,
        accountId
      }

      if (id === 'new') {
        await getClient().graphql({
          query: CREATE_REPORT_CONFIGURATION,
          variables: { input }
        })
        toast.success('Report configuration created')
      } else {
        await getClient().graphql({
          query: UPDATE_REPORT_CONFIGURATION,
          variables: {
            input: {
              ...input,
              id
            }
          }
        })
        toast.success('Report configuration updated')
      }

      router.push('/lab/reports/edit')
    } catch (err: any) {
      console.error('Error saving report configuration:', err)
      toast.error('Failed to save report configuration')
    }
  }

  const handleBack = () => {
    router.push('/lab/reports/edit')
  }

  if (isLoading) {
    return <div>Loading...</div>
  }

  if (error) {
    return (
      <div className="space-y-4 p-4">
        <h1 className="text-2xl font-bold">Edit Report Configuration</h1>
        <div className="text-sm text-destructive">{error}</div>
        <Button onClick={handleBack}>Back</Button>
      </div>
    )
  }

  if (!configuration) {
    return <div>Configuration not found</div>
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header Area */}
      <div className="flex-none p-3">
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={handleBack}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <h1 className="text-xl font-semibold">Edit Report Configuration</h1>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={!hasChanges}>
              <Save className="mr-2 h-4 w-4"/> Save
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content Area - Now uses flex-1 to fill remaining space */}
      <div className="flex-1 flex flex-col p-3 min-h-0">
        {/* Form Fields - Fixed height section */}
        <div className="flex-none space-y-2 mb-4">
          <Input
            value={configuration.name}
            onChange={(e) => {
              setConfiguration(prev => prev ? { ...prev, name: e.target.value } : null)
              setHasChanges(true)
            }}
            className="text-lg font-semibold bg-background border-0 px-2 h-auto w-full
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="Configuration Name"
          />
          <Input
            value={configuration.description || ''}
            onChange={(e) => {
              setConfiguration(prev => prev ? { ...prev, description: e.target.value } : null)
              setHasChanges(true)
            }}
            className="bg-background border-0 px-2 h-auto w-full
                     focus-visible:ring-0 focus-visible:ring-offset-0 
                     placeholder:text-muted-foreground rounded-md"
            placeholder="Description (optional)"
          />
        </div>

        {/* Editor Container - Takes up remaining space */}
        <div className="flex-1 border rounded-md overflow-hidden min-h-0">
          <Editor
            height="100%"
            defaultLanguage="yaml"
            value={configuration.configuration}
            onChange={(value) => {
              if (!value) return
              setConfiguration(prev => prev ? { ...prev, configuration: value } : null)
              setHasChanges(true)
            }}
            onMount={(editor, monaco) => {
              editorInstanceRef.current = editor
              monacoRef.current = monaco
              defineCustomMonacoThemes(monaco)
              applyMonacoTheme(monaco)
              editor.layout()
            }}
            options={getCommonMonacoOptions()}
          />
        </div>
      </div>
    </div>
  )
} 
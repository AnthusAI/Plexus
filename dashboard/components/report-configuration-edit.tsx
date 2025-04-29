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
  const [editorHeight, setEditorHeight] = useState(500)
  const [isEditorFullscreen, setIsEditorFullscreen] = useState(false)
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

  // Define custom Monaco theme
  const defineCustomTheme = useCallback((monaco: Monaco) => {
    const getCssVar = (name: string) => {
      const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
      if (value.startsWith('hsl(')) {
        const tempEl = document.createElement('div')
        tempEl.style.color = value
        document.body.appendChild(tempEl)
        const computedColor = getComputedStyle(tempEl).color
        document.body.removeChild(tempEl)
        if (computedColor.startsWith('rgb')) {
          const rgbValues = computedColor.match(/\d+/g)
          if (rgbValues && rgbValues.length >= 3) {
            const hex = rgbValues.slice(0, 3).map(x => {
              const hex = parseInt(x).toString(16)
              return hex.length === 1 ? '0' + hex : hex
            }).join('')
            return hex
          }
        }
      }
      if (value.startsWith('#')) {
        return value.substring(1)
      }
      return value
    }

    const commonRules = [
      { token: 'comment', foreground: getCssVar('--muted-foreground'), fontStyle: 'italic' },
      { token: 'type', foreground: getCssVar('--primary') },
      { token: 'key', foreground: getCssVar('--primary') },
      { token: 'string', foreground: getCssVar('--foreground') },
      { token: 'number', foreground: getCssVar('--foreground') },
      { token: 'boolean', foreground: getCssVar('--foreground') },
      { token: 'delimiter', foreground: getCssVar('--muted-foreground') },
      { token: 'bracket', foreground: getCssVar('--muted-foreground') },
      { token: 'keyword', foreground: getCssVar('--accent') },
      { token: 'identifier', foreground: getCssVar('--foreground') },
      { token: 'tag', foreground: getCssVar('--primary') },
      { token: 'number.yaml', foreground: getCssVar('--foreground') },
      { token: 'string.yaml', foreground: getCssVar('--foreground') },
      { token: 'keyword.yaml', foreground: getCssVar('--accent') },
    ]

    monaco.editor.defineTheme('plexusLightTheme', {
      base: 'vs',
      inherit: true,
      rules: commonRules,
      colors: {
        'editor.background': '#' + getCssVar('--background'),
        'editor.foreground': '#' + getCssVar('--foreground'),
        'editor.lineHighlightBackground': '#' + getCssVar('--muted'),
        'editorLineNumber.foreground': '#' + getCssVar('--muted-foreground'),
        'editor.selectionBackground': '#' + getCssVar('--primary'),
        'editorIndentGuide.background': '#' + getCssVar('--border'),
        'editor.selectionHighlightBackground': '#' + getCssVar('--muted'),
        'editorCursor.foreground': '#' + getCssVar('--foreground'),
        'editorWhitespace.foreground': '#' + getCssVar('--border'),
        'editorLineNumber.activeForeground': '#' + getCssVar('--foreground'),
      }
    } as editor.IStandaloneThemeData)

    monaco.editor.defineTheme('plexusDarkTheme', {
      base: 'vs-dark',
      inherit: true,
      rules: commonRules,
      colors: {
        'editor.background': '#' + getCssVar('--background'),
        'editor.foreground': '#' + getCssVar('--foreground'),
        'editor.lineHighlightBackground': '#' + getCssVar('--muted'),
        'editorLineNumber.foreground': '#' + getCssVar('--muted-foreground'),
        'editor.selectionBackground': '#' + getCssVar('--primary'),
        'editorIndentGuide.background': '#' + getCssVar('--border'),
        'editor.selectionHighlightBackground': '#' + getCssVar('--muted'),
        'editorCursor.foreground': '#' + getCssVar('--foreground'),
        'editorWhitespace.foreground': '#' + getCssVar('--border'),
        'editorLineNumber.activeForeground': '#' + getCssVar('--foreground'),
      }
    } as editor.IStandaloneThemeData)
  }, [])

  // Apply theme changes
  useEffect(() => {
    const applyTheme = () => {
      if (!monacoRef.current) return
      const isDarkMode = document.documentElement.classList.contains('dark')
      defineCustomTheme(monacoRef.current)
      monacoRef.current.editor.setTheme(isDarkMode ? 'plexusDarkTheme' : 'plexusLightTheme')
    }

    applyTheme()
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          applyTheme()
        }
      })
    })
    observer.observe(document.documentElement, { attributes: true })
    return () => observer.disconnect()
  }, [defineCustomTheme])

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
      <div className="flex-none p-1.5">
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

      {/* Main Content Area */}
      <div className="flex-1 p-1.5 overflow-y-auto">
        <div className="space-y-4">
          <div className="space-y-2">
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

          <div className="border rounded-md overflow-hidden">
            <Editor
              height={editorHeight}
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
                defineCustomTheme(monaco)
                const isDarkMode = document.documentElement.classList.contains('dark')
                monaco.editor.setTheme(isDarkMode ? 'plexusDarkTheme' : 'plexusLightTheme')
                editor.layout()
              }}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                wordWrap: 'on',
                wrappingIndent: 'indent',
                automaticLayout: true,
                fontFamily: 'monospace',
                fontLigatures: true,
                contextmenu: true,
                cursorBlinking: 'smooth',
                cursorSmoothCaretAnimation: 'on',
                smoothScrolling: true,
                renderLineHighlight: 'all',
                colorDecorators: true
              }}
            />
          </div>
        </div>
      </div>
    </div>
  )
} 
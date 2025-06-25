"use client"

import React, { useState, useEffect } from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Plus, Pencil, Trash2, ChevronLeft, Copy } from "lucide-react"
import { format, formatDistanceToNow } from "date-fns"
import { useRouter } from 'next/navigation'
import { getClient } from '@/utils/amplify-client'
import type { GraphQLResult } from '@aws-amplify/api'
import { toast } from "sonner"
import { useAuthenticator } from '@aws-amplify/ui-react'
import { useTranslations } from "@/app/contexts/TranslationContext"

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

// GraphQL query to list report configurations
const LIST_REPORT_CONFIGURATIONS = `
  query ListReportConfigurations($accountId: String!) {
    listReportConfigurations(filter: { accountId: { eq: $accountId } }) {
      items {
        id
        name
        description
        configuration
        accountId
        createdAt
        updatedAt
      }
    }
  }
`

// GraphQL mutation to delete a report configuration
const DELETE_REPORT_CONFIGURATION = `
  mutation DeleteReportConfiguration($input: DeleteReportConfigurationInput!) {
    deleteReportConfiguration(input: $input) {
      id
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

const ACCOUNT_KEY = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY || 'call-criteria'

export function ReportConfigurationsDashboard() {
  const t = useTranslations('reports');
  const { user } = useAuthenticator()
  const router = useRouter()
  const [configurations, setConfigurations] = useState<ReportConfiguration[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [accountId, setAccountId] = useState<string | null>(null)

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

  // Define fetchConfigurations function outside useEffect
  const fetchConfigurations = async () => {
    if (!accountId) return

    setIsLoading(true)
    setError(null)
    try {
      const response = await getClient().graphql<GraphQLResult<{
        listReportConfigurations: {
          items: ReportConfiguration[]
        }
      }>>({
        query: LIST_REPORT_CONFIGURATIONS,
        variables: {
          accountId
        }
      })

      if ('data' in response && response.data?.listReportConfigurations?.items) {
        setConfigurations(response.data.listReportConfigurations.items)
      }
    } catch (err: any) {
      console.error('Error fetching report configurations:', err)
      setError(`Error fetching report configurations: ${err.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  // Fetch report configurations on mount or when accountId changes
  useEffect(() => {
    fetchConfigurations() // Call the function defined above
  }, [accountId])

  const handleCreate = () => {
    router.push('/lab/reports/edit/new')
  }

  const handleEdit = (id: string) => {
    router.push(`/lab/reports/edit/${id}`)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this report configuration?')) {
      return
    }

    try {
      await getClient().graphql({
        query: DELETE_REPORT_CONFIGURATION,
        variables: {
          input: { id }
        }
      })

      setConfigurations(prev => prev.filter(config => config.id !== id))
      toast.success('Report configuration deleted')
    } catch (err: any) {
      console.error('Error deleting report configuration:', err)
      toast.error('Failed to delete report configuration')
    }
  }

  const handleDuplicate = async (config: ReportConfiguration) => {
    if (!accountId) return

    try {
      const response = await getClient().graphql<GraphQLResult<{
        createReportConfiguration: ReportConfiguration
      }>>({
        query: CREATE_REPORT_CONFIGURATION,
        variables: {
          input: {
            name: `${config.name} copy`,
            description: config.description,
            configuration: config.configuration,
            accountId: accountId
          }
        }
      })

      if ('data' in response && response.data?.createReportConfiguration) {
        const newConfig = response.data.createReportConfiguration
        setConfigurations(prev => [newConfig, ...prev])
        toast.success('Report configuration duplicated')
      }
    } catch (err: any) {
      console.error('Error duplicating report configuration:', err)
      toast.error('Failed to duplicate report configuration')
    }
  }

  if (isLoading) {
    return <div>Loading...</div>
  }

  if (error) {
    return (
      <div className="space-y-4 p-4">
        <h1 className="text-2xl font-bold">{t('reportConfigurations')}</h1>
        <div className="text-sm text-destructive">{error}</div>
        <Button onClick={() => accountId && fetchConfigurations()}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header Area */}
      <div className="flex-none p-1.5">
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push('/lab/reports')}
              aria-label="Back to reports"
            >
              <ChevronLeft className="h-6 w-6" />
            </Button>
            <div>
              <h1 className="text-xl font-semibold">{t('reportConfigurations')}</h1>
              {error && <p className="text-xs text-destructive">{error}</p>}
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4"/> New Configuration
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-1.5 overflow-y-auto">
        <div className="grid gap-3 grid-cols-1 @[640px]:grid-cols-2">
          {configurations.map((config) => (
            <Card key={config.id} className="cursor-pointer hover:bg-accent/5 border-0 shadow-none">
              <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                <div className="space-y-1">
                  <h3 className="font-semibold">{config.name}</h3>
                  {config.description && (
                    <p className="text-sm text-muted-foreground">
                      {config.description}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleEdit(config.id)
                    }}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDuplicate(config)
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDelete(config.id)
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground">
                  Last updated {formatDistanceToNow(new Date(config.updatedAt), { addSuffix: true })}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
} 
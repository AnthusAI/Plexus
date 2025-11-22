import React, { useEffect, useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { ModelListResult } from '@/types/shared'
import { listFromModel } from "@/utils/amplify-helpers"

export const client = generateClient<Schema>()

export interface ReportConfigurationSelectorProps {
  selectedReportConfiguration: string | null;
  setSelectedReportConfiguration: (value: string | null) => void;
  useMockData?: boolean;
}

async function listReportConfigurations(accountId: string): ModelListResult<Schema['ReportConfiguration']['type']> {
  return listFromModel<Schema['ReportConfiguration']['type']>(
    client.models.ReportConfiguration,
    { accountId: { eq: accountId } }
  )
}

const ReportConfigurationSelector: React.FC<ReportConfigurationSelectorProps> = ({ 
  selectedReportConfiguration, 
  setSelectedReportConfiguration,
  useMockData = false
}) => {
  const [reportConfigurations, setReportConfigurations] = useState<Array<{ value: string; label: string }>>([])
  const [isLoading, setIsLoading] = useState(!useMockData)
  const [accountId, setAccountId] = useState<string | null>(null)

  // Fetch account ID first (similar to Reports Dashboard)
  useEffect(() => {
    const fetchAccountId = async () => {
      try {
        const ACCOUNT_KEY = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY || ''
        const accountResponse = await client.graphql({
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
        }
      } catch (err: any) {
        console.error('Error fetching account:', err)
      }
    }
    
    if (!useMockData) {
      fetchAccountId()
    }
  }, [useMockData])

  // Fetch report configurations when accountId is available
  useEffect(() => {
    if (useMockData || !accountId) return

    async function fetchReportConfigurations() {
      try {
        setIsLoading(true)
        if (!accountId) return
        const { data: configModels } = await listReportConfigurations(accountId)
        
        // Sort by updatedAt descending (most recent first)
        const sortedConfigs = configModels.sort((a, b) => {
          const aDate = new Date(a.updatedAt || a.createdAt || '').getTime()
          const bDate = new Date(b.updatedAt || b.createdAt || '').getTime()
          return bDate - aDate // Descending order
        })
        
        const formattedConfigurations = sortedConfigs.map(config => ({
          value: config.id,
          label: config.name || `Config ${config.id.substring(0, 6)}`
        }))
        
        setReportConfigurations(formattedConfigurations)
      } catch (error) {
        console.error('Error fetching report configurations:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchReportConfigurations()
  }, [accountId, useMockData])

  const handleConfigurationChange = (value: string) => {
    setSelectedReportConfiguration(value === "all" ? null : value);
  };

  return (
    <div className="flex flex-wrap gap-2">
      <Select 
        onValueChange={handleConfigurationChange}
        value={selectedReportConfiguration || "all"}
        disabled={isLoading}
      >
        <SelectTrigger className="w-[200px] h-8 bg-card border-none focus:ring-0 focus:ring-offset-0 focus:outline-none">
          <SelectValue placeholder={isLoading ? "Loading..." : "Report Configuration"} />
        </SelectTrigger>
        <SelectContent className="bg-card border-none focus:ring-0 focus:ring-offset-0 focus:outline-none">
          <SelectItem value="all">All Report Configurations</SelectItem>
          {reportConfigurations.map(config => (
            <SelectItem key={config.value} value={config.value}>
              {config.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export default ReportConfigurationSelector
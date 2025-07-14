import React, { useEffect, useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { ModelListResult } from '@/types/shared'
import { listFromModel } from "@/utils/amplify-helpers"

import { useAccount } from "@/app/contexts/AccountContext"

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
  const { selectedAccount } = useAccount()
  const [reportConfigurations, setReportConfigurations] = useState<Array<{ value: string; label: string }>>([])
  const [isLoading, setIsLoading] = useState(!useMockData)

  // Debug logging
  useEffect(() => {
    console.debug('ReportConfigurationSelector state:', { 
      selectedReportConfiguration, 
      configsCount: reportConfigurations.length,
      configs: reportConfigurations.map(c => ({ id: c.value, name: c.label }))
    });
  }, [selectedReportConfiguration, reportConfigurations]);

  // Fetch report configurations when accountId is available
  useEffect(() => {
    if (useMockData || !selectedAccount) return

    async function fetchReportConfigurations() {
      try {
        setIsLoading(true)
        if (!selectedAccount) return
        const { data: configModels } = await listReportConfigurations(selectedAccount.id)
        
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
  }, [selectedAccount, useMockData])

  const handleConfigurationChange = (value: string) => {
    console.debug('Report configuration selection changed:', { 
      newValue: value, 
      previousValue: selectedReportConfiguration 
    });
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
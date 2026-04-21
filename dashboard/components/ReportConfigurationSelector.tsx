import React, { useEffect, useState } from "react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useAccount } from "@/app/contexts/AccountContext"
import { listAllReportConfigurationsByAccount } from "@/utils/report-configurations"

export interface ReportConfigurationSelectorProps {
  selectedReportConfiguration: string | null;
  setSelectedReportConfiguration: (value: string | null) => void;
  useMockData?: boolean;
}

const ReportConfigurationSelector: React.FC<ReportConfigurationSelectorProps> = ({
  selectedReportConfiguration,
  setSelectedReportConfiguration,
  useMockData = false
}) => {
  const { selectedAccount, isLoadingAccounts } = useAccount()
  const [reportConfigurations, setReportConfigurations] = useState<Array<{ value: string; label: string }>>([])
  const [isLoading, setIsLoading] = useState(!useMockData)
  const accountId = selectedAccount?.id || null

  // Fetch report configurations when accountId is available
  useEffect(() => {
    if (useMockData) return
    if (!accountId) {
      setReportConfigurations([])
      setIsLoading(isLoadingAccounts)
      return
    }

    async function fetchReportConfigurations() {
      try {
        setIsLoading(true)
        if (!accountId) return
        const deduped = await listAllReportConfigurationsByAccount(accountId)

        const formattedConfigurations = deduped.map(config => ({
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
  }, [accountId, isLoadingAccounts, useMockData])

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

"use client"

import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  Label,
  Button,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../types"
import { TaskDialogProps } from "../types"
import { CardButton } from "@/components/CardButton"
import { X } from "lucide-react"
import { getClient } from "@/utils/amplify-client"
import { toast } from "sonner"
import { ConfigurableParametersDialog } from "@/components/ui/ConfigurableParametersDialog"
import { parseParametersFromYaml, hasParameters } from "@/lib/parameter-parser"

// Report configuration type definition
interface ReportConfiguration {
  id: string
  name: string
  description?: string | null
  configuration?: string | null
}

// GraphQL query to list report configurations
const LIST_REPORT_CONFIGURATIONS = `
  query ListReportConfigurations($accountId: String!) {
    listReportConfigurationByAccountIdAndUpdatedAt(
      accountId: $accountId
      limit: 100
    ) {
      items {
        id
        name
        description
      }
    }
  }
`

// GraphQL query to get full report configuration with content
const GET_REPORT_CONFIGURATION = `
  query GetReportConfiguration($id: ID!) {
    getReportConfiguration(id: $id) {
      id
      name
      description
      configuration
    }
  }
`

export function ReportConfigurationDialog({ action, isOpen, onClose, onDispatch }: TaskDialogProps) {
  const [configurations, setConfigurations] = useState<ReportConfiguration[]>([])
  const [selectedConfigId, setSelectedConfigId] = useState<string>("")
  const [selectedConfig, setSelectedConfig] = useState<ReportConfiguration | null>(null)
  const [showParametersDialog, setShowParametersDialog] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  
  // Fetch report configurations
  useEffect(() => {
    const fetchConfigurations = async () => {
      if (!isOpen) return
      
      setIsLoading(true)
      setError(null)
      
      try {
        // First get the account ID
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
            filter: { key: { eq: process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY || '' } }
          }
        })
        
        if ('data' in accountResponse && accountResponse.data?.listAccounts?.items?.length) {
          const accountId = accountResponse.data.listAccounts.items[0].id
          
          // Then fetch report configurations for that account
          const configResponse = await getClient().graphql({
            query: LIST_REPORT_CONFIGURATIONS,
            variables: {
              accountId
            }
          })
          
          if ('data' in configResponse && 
              configResponse.data?.listReportConfigurationByAccountIdAndUpdatedAt?.items) {
            const configs = configResponse.data.listReportConfigurationByAccountIdAndUpdatedAt.items
            setConfigurations(configs)
            
            // Auto-select the first config if none is selected
            if (configs.length > 0 && !selectedConfigId) {
              setSelectedConfigId(configs[0].id)
            }
          } else {
            setError("No report configurations found")
          }
        } else {
          setError("Account not found")
        }
      } catch (err: any) {
        console.error('Error fetching report configurations:', err)
        setError(`Error: ${err.message}`)
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchConfigurations()
  }, [isOpen, selectedConfigId])
  
  // Fetch full configuration when selected config changes
  useEffect(() => {
    const fetchFullConfiguration = async () => {
      if (!selectedConfigId) {
        setSelectedConfig(null)
        return
      }
      
      
      try {
        const response = await getClient().graphql({
          query: GET_REPORT_CONFIGURATION,
          variables: { id: selectedConfigId }
        })
        
        
        if ('data' in response && response.data?.getReportConfiguration) {
          const config = response.data.getReportConfiguration
          setSelectedConfig(config)
        } else {
        }
      } catch (err) {
        console.error('Error fetching report configuration:', err)
      }
    }
    
    fetchFullConfiguration()
  }, [selectedConfigId])
  
  const handleRunReport = async () => {
    if (!selectedConfigId) {
      toast.error("Please select a report configuration")
      return
    }
    
    
    // Check if this configuration has parameters
    if (selectedConfig?.configuration && hasParameters(selectedConfig.configuration)) {
      // Show parameters dialog
      setShowParametersDialog(true)
    } else {
      // Run directly without parameters
      handleDispatchReport()
    }
  }
  
  const handleDispatchReport = (parameters?: Record<string, any>) => {
    if (!selectedConfigId) return
    
    // Build the command for running this report
    let command = `report run --config ${selectedConfigId}`
    
    // Add parameter options if provided
    if (parameters) {
      Object.entries(parameters).forEach(([key, value]) => {
        command += ` --param-${key}=${value}`
      })
    }
    
    // Get additional metadata
    const metadata = {
      reportConfigurationId: selectedConfigId,
      reportConfigurationName: selectedConfig?.name || 'Report',
      parameters: parameters || {}
    }
    
    // Dispatch the task with metadata
    onDispatch(command, 'report')
    onClose()
  }
  
  const handleParametersSubmit = (parameters: Record<string, any>) => {
    setShowParametersDialog(false)
    handleDispatchReport(parameters)
  }
  
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-card border-0" hideCloseButton>
        <div className="absolute right-4 top-4">
          <CardButton
            icon={X}
            onClick={onClose}
            aria-label="Close"
          />
        </div>
        <DialogHeader>
          <div className="flex items-center gap-2">
            {action.icon}
            <DialogTitle>{action.name}</DialogTitle>
          </div>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          {error && (
            <div className="text-sm text-destructive p-2 rounded bg-destructive/10">
              {error}
            </div>
          )}
          
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="reportConfiguration" className="text-right">
              Report Configuration
            </Label>
            <div className="col-span-3">
              <Select
                value={selectedConfigId}
                onValueChange={setSelectedConfigId}
                disabled={isLoading || configurations.length === 0}
              >
                <SelectTrigger className="col-span-3 border-0 bg-background" tabIndex={-1}>
                  <SelectValue placeholder="Select a report configuration" />
                </SelectTrigger>
                <SelectContent className="border-0 bg-background">
                  {configurations.map(config => (
                    <SelectItem key={config.id} value={config.id}>
                      {config.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedConfigId && (
                <p className="text-xs text-muted-foreground mt-1">
                  {configurations.find(c => c.id === selectedConfigId)?.description || ''}
                </p>
              )}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} className="bg-border border-0" tabIndex={-1}>
            Cancel
          </Button>
          <Button 
            onClick={handleRunReport} 
            className="border-0" 
            tabIndex={-1}
            disabled={!selectedConfigId || isLoading}
          >
            Run Report
          </Button>
        </DialogFooter>
      </DialogContent>
      
      {/* Parameters Dialog */}
      {selectedConfig && selectedConfig.configuration && (
        <ConfigurableParametersDialog
          open={showParametersDialog}
          onOpenChange={(open) => {
            setShowParametersDialog(open)
            if (!open) {
              // User cancelled parameters - close main dialog too
              onClose()
            }
          }}
          title={`Configure ${selectedConfig.name}`}
          description="Please provide the required parameters for this report"
          parameters={parseParametersFromYaml(selectedConfig.configuration)}
          onSubmit={handleParametersSubmit}
          submitLabel="Run Report"
        />
      )}
    </Dialog>
  )
} 
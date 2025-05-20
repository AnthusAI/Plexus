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

// Report configuration type definition
interface ReportConfiguration {
  id: string
  name: string
  description?: string | null
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

export function ReportConfigurationDialog({ action, isOpen, onClose, onDispatch }: TaskDialogProps) {
  const [configurations, setConfigurations] = useState<ReportConfiguration[]>([])
  const [selectedConfigId, setSelectedConfigId] = useState<string>("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Fetch report configurations
  useEffect(() => {
    const fetchConfigurations = async () => {
      if (!isOpen) return
      
      setIsLoading(true)
      setError(null)
      
      try {
        // First get the account ID - using call-criteria as default
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
            filter: { key: { eq: 'call-criteria' } }
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
  
  const handleDispatch = () => {
    if (!selectedConfigId) {
      toast.error("Please select a report configuration")
      return
    }
    
    // Get the selected configuration
    const selectedConfig = configurations.find(c => c.id === selectedConfigId)
    
    // Build the command for running this report
    const command = `report run --config-id ${selectedConfigId}`
    
    // Get additional metadata
    const metadata = {
      reportConfigurationId: selectedConfigId,
      reportConfigurationName: selectedConfig?.name || 'Report'
    }
    
    // Dispatch the task with metadata
    onDispatch(command, 'report');
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
            onClick={handleDispatch} 
            className="border-0" 
            tabIndex={-1}
            disabled={!selectedConfigId || isLoading}
          >
            Run Report
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
} 
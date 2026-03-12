"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Play } from "lucide-react"
import { createTask } from "@/utils/data-operations"
import { toast } from "sonner"
import { ReportConfigurationDialog } from "./dialogs/ReportConfigurationDialog"
import { useAccount } from "@/app/contexts/AccountContext"

export function RunReportButton() {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const { selectedAccount } = useAccount()

  const handleOpenDialog = () => {
    setIsModalOpen(true)
  }

  const handleCloseDialog = () => {
    setIsModalOpen(false)
  }

  const handleDispatch = async (commandStr: string, target?: string) => {
    console.log('Dispatching report task with command:', commandStr, 'target:', target);

    try {
      setIsLoading(true);
      const task = await createTask({
        type: 'report run',
        target: target || 'report',
        command: commandStr,
        accountId: selectedAccount?.id || 'call-criteria',
        dispatchStatus: 'PENDING',
        status: 'PENDING'
      });
      
      if (task) {
        toast.success("Report generation started", {
          description: <span className="font-mono text-sm truncate block">{commandStr}</span>
        });
      } else {
        toast.error("Failed to start report generation");
      }
    } catch (error) {
      console.error("Error dispatching report task:", error);
      toast.error("Error starting report generation");
    } finally {
      setIsLoading(false);
    }
    handleCloseDialog();
  };

  // Mock action object for the dialog
  const mockAction = {
    name: "Run Report",
    icon: <Play className="mr-2 h-4 w-4" />,
    command: "report run",
    target: "report",
    dialogType: "reportConfiguration"
  };

  return (
    <>
      <Button 
        onClick={handleOpenDialog}
        disabled={isLoading}
        variant="ghost" 
        className="bg-card hover:bg-accent text-muted-foreground"
      >
        <Play className="mr-2 h-4 w-4" /> Run Report
      </Button>

      <ReportConfigurationDialog
        action={mockAction}
        isOpen={isModalOpen}
        onClose={handleCloseDialog}
        onDispatch={handleDispatch}
      />
    </>
  )
} 
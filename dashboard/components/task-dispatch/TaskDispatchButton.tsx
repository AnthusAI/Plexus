"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { ChevronDown } from "lucide-react"
import { createTask } from "@/utils/data-operations"
import { toast } from "sonner"
import { TaskAction, TaskDispatchConfig } from "./types"

export function TaskDispatchButton({ config }: { config: TaskDispatchConfig }) {
  const [selectedAction, setSelectedAction] = useState<TaskAction | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)

  const handleActionSelect = (action: TaskAction) => {
    setSelectedAction(action)
    setIsModalOpen(true)
    setIsDropdownOpen(false)
  }

  const handleCloseDialog = () => {
    setIsModalOpen(false)
    setSelectedAction(null)
    setIsDropdownOpen(false)
  }

  const handleDispatch = async (command: string, target?: string) => {
    try {
      if (!selectedAction) return

      const type = selectedAction.name === 'Accuracy' ? 'Accuracy Evaluation' : selectedAction.name.toLowerCase()

      const task = await createTask(
        command,
        type,
        target || selectedAction.target
      )
      
      if (task) {
        toast.success("Task announced", {
          description: <span className="font-mono text-sm truncate block">{command}</span>
        })
      } else {
        toast.error("Failed to dispatch task")
      }
    } catch (error) {
      console.error("Error dispatching task:", error)
      toast.error("Error dispatching task")
    }
    handleCloseDialog()
  }

  // Get the dialog component for the selected action
  const DialogComponent = selectedAction ? config.dialogs[selectedAction.dialogType] : null

  return (
    <>
      <DropdownMenu open={isDropdownOpen} onOpenChange={setIsDropdownOpen}>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="bg-card hover:bg-accent">
            {config.buttonLabel} <ChevronDown className="ml-2 h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          {config.actions.map((action) => (
            <DropdownMenuItem key={action.name} onSelect={() => handleActionSelect(action)}>
              {action.icon}
              {action.name}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {DialogComponent && selectedAction && (
        <DialogComponent
          action={selectedAction}
          isOpen={isModalOpen}
          onClose={handleCloseDialog}
          onDispatch={handleDispatch}
        />
      )}
    </>
  )
} 
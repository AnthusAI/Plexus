"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { PlayCircle, ClipboardCheck, Zap, ChevronDown } from "lucide-react"
import { createTask } from "@/utils/data-operations"
import { toast } from "sonner"

type Action = {
  name: string
  icon: React.ReactNode
  command: string
  target?: string
}

const actions: Action[] = [
  { 
    name: "Demo", 
    icon: <PlayCircle className="mr-2 h-4 w-4" />,
    command: "command demo"
  },
  { 
    name: "Evaluation", 
    icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
    command: "evaluate accuracy",
    target: "evaluation"
  },
  { 
    name: "Optimization", 
    icon: <Zap className="mr-2 h-4 w-4" />,
    command: "optimize",
    target: "optimization"
  },
]

export function TaskDispatchButton() {
  const [selectedAction, setSelectedAction] = useState<Action | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [command, setCommand] = useState("")
  const [target, setTarget] = useState("")

  const handleActionSelect = (action: Action) => {
    setSelectedAction(action)
    setCommand(action.command)
    setTarget(action.target || "")
    setIsModalOpen(true)
    setIsDropdownOpen(false)
  }

  const handleCloseDialog = () => {
    setIsModalOpen(false)
    setCommand("")
    setTarget("")
    setSelectedAction(null)
    setIsDropdownOpen(false)
  }

  const handleDispatch = async () => {
    try {
      const task = await createTask(command, selectedAction?.name.toLowerCase() || "command", target)
      if (task) {
        toast.success("Task dispatched successfully")
      } else {
        toast.error("Failed to dispatch task")
      }
    } catch (error) {
      console.error("Error dispatching task:", error)
      toast.error("Error dispatching task")
    }
    handleCloseDialog()
  }

  return (
    <>
      <DropdownMenu open={isDropdownOpen} onOpenChange={setIsDropdownOpen}>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="bg-card hover:bg-accent">
            Actions <ChevronDown className="ml-2 h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          {actions.map((action) => (
            <DropdownMenuItem key={action.name} onSelect={() => handleActionSelect(action)}>
              {action.icon}
              {action.name}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={isModalOpen} onOpenChange={handleCloseDialog}>
        <DialogContent autoFocus={false} className="bg-card border-0">
          <DialogHeader>
            <DialogTitle>{selectedAction?.name} Action</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="command" className="text-right">
                Command
              </Label>
              <Input
                id="command"
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                className="col-span-3 font-mono bg-background"
                tabIndex={-1}
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="target" className="text-right">
                Target
              </Label>
              <Input
                id="target"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="col-span-3 font-mono bg-background"
                tabIndex={-1}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              Cancel
            </Button>
            <Button onClick={handleDispatch}>Dispatch</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
} 
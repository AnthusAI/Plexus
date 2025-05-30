"use client"

import { useState } from "react"
import { toast } from "sonner"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  Label,
  Button,
  Input
} from "../types"
import { TaskDialogProps } from "../types"
import { commands, CommandType } from "../configs/commands"
import { CardButton } from "@/components/CardButton"
import { X } from "lucide-react"

// Type guard for simple commands
function isSimpleCommand(command: any): command is { type: 'simple', generate: () => string } {
  return command && typeof command === 'object' && command.type === 'simple' && typeof command.generate === 'function'
}

export function SimpleDialog({ action, isOpen, onClose, onDispatch }: TaskDialogProps) {
  const [command, setCommand] = useState(action.command as string)

  const handleDispatch = () => {
    // If command is a string, use it directly
    if (typeof action.command === 'string') {
      onDispatch(action.command, action.target)
      onClose()
      return
    }

    // Otherwise try to use command generator
    const commandType = action.name.toLowerCase() as CommandType
    
    if (commandType === 'evaluation') {
      console.error('Evaluation commands should use EvaluationDialog')
      return
    }
    
    const generator = commands[commandType as Exclude<CommandType, 'evaluation'>]
    if (!isSimpleCommand(generator)) {
      console.error('Invalid command type:', commandType)
      return
    }

    const generatedCommand = generator.generate()
    onDispatch(generatedCommand, action.target)
    onClose()
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
          <DialogTitle>{action.name} Action</DialogTitle>
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
              className="col-span-3 font-mono bg-background border-0"
              tabIndex={-1}
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck="false"
              readOnly
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} className="bg-border border-0" tabIndex={-1}>
            Cancel
          </Button>
          <Button onClick={handleDispatch} className="border-0" tabIndex={-1}>Run Command</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
} 
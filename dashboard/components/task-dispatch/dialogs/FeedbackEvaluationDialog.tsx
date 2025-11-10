"use client"

import { useState } from "react"
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
import { CardButton } from "@/components/CardButton"
import { X } from "lucide-react"

interface FeedbackEvaluationOptions {
  scorecardName: string
  scoreName: string
  days: number
}

export function FeedbackEvaluationDialog({ action, isOpen, onClose, onDispatch, initialOptions }: TaskDialogProps & { initialOptions?: Partial<FeedbackEvaluationOptions> }) {
  const [options, setOptions] = useState<FeedbackEvaluationOptions>({
    scorecardName: initialOptions?.scorecardName || 'termlifev1',
    scoreName: initialOptions?.scoreName || 'Assumptive Close',
    days: initialOptions?.days || 7
  })

  const handleDispatch = () => {
    // Build the feedback evaluation command
    const args = [
      `--scorecard "${options.scorecardName}"`,
      `--score "${options.scoreName}"`,
      `--days ${options.days}`
    ].filter(Boolean).join(' ')
    
    const command = `evaluate feedback ${args}`
    console.log('Generated feedback evaluation command:', command)
    onDispatch(command, action.target)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-card border-0" hideCloseButton>
        <DialogHeader className="pb-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-xl font-semibold">Evaluate Feedback</DialogTitle>
            <CardButton
              icon={X}
              onClick={onClose}
              aria-label="Close"
            />
          </div>
        </DialogHeader>
        <div className="grid gap-6 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="scorecardName" className="text-right">
              Scorecard
            </Label>
            <Input
              id="scorecardName"
              value={options.scorecardName}
              onChange={(e) => setOptions({ ...options, scorecardName: e.target.value })}
              className="col-span-3 border-0 bg-background"
              tabIndex={-1}
            />
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="scoreName" className="text-right">
              Score
            </Label>
            <Input
              id="scoreName"
              value={options.scoreName}
              onChange={(e) => setOptions({ ...options, scoreName: e.target.value })}
              className="col-span-3 border-0 bg-background"
              tabIndex={-1}
            />
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="days" className="text-right">
              Days to Look Back
            </Label>
            <Input
              id="days"
              type="number"
              value={options.days}
              onChange={(e) => setOptions({ ...options, days: parseInt(e.target.value) || 7 })}
              className="col-span-3 border-0 bg-background"
              min={1}
              max={365}
              tabIndex={-1}
            />
          </div>

          <div className="text-sm text-muted-foreground px-4">
            <p className="mb-2">This will analyze feedback items from the last {options.days} days for the selected score.</p>
            <p>Calculates agreement metrics (AC1), accuracy, precision, and recall based on human corrections.</p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} className="bg-border border-0" tabIndex={-1}>
            Cancel
          </Button>
          <Button onClick={handleDispatch} className="border-0" tabIndex={-1}>Run Evaluation</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

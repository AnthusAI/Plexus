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
import { SampleSizeInput } from "../components/SampleSizeInput"
import { commands, EvaluationType } from "../configs/commands"
import { CardButton } from "@/components/CardButton"
import { X } from "lucide-react"

interface EvaluationOptions {
  scorecardName: string
  scoreName: string
  numberOfSamples: number
  versionId?: string
}

export function EvaluationDialog({ action, isOpen, onClose, onDispatch, initialOptions }: TaskDialogProps & { initialOptions?: Partial<EvaluationOptions> }) {
  const [options, setOptions] = useState<EvaluationOptions>({
    scorecardName: initialOptions?.scorecardName || 'example-scorecard',
    scoreName: initialOptions?.scoreName || 'Example Score',
    numberOfSamples: initialOptions?.numberOfSamples || 10,
    versionId: initialOptions?.versionId
  })

  const handleDispatch = () => {
    // Extract evaluation type from action name by removing "Evaluate " prefix and converting to lowercase
    const evaluationType = action.name.replace(/^Evaluate\s+/, '').toLowerCase() as EvaluationType
    const generator = commands.evaluation[evaluationType]
    
    if (!generator || generator.type !== 'complex') {
      console.error('Invalid evaluation type:', evaluationType)
      return
    }

    onDispatch({ ...options }, action.target)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-card border-0 sm:max-w-2xl" hideCloseButton>
        <DialogHeader className="pb-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-xl font-semibold">{action.name}</DialogTitle>
            <CardButton
              icon={X}
              onClick={onClose}
              aria-label="Close"
            />
          </div>
        </DialogHeader>
        <div className="flex flex-col gap-6 py-4">
          <div className="grid grid-cols-[9rem_minmax(0,1fr)] items-center gap-4">
            <Label htmlFor="scorecardName" className="text-right leading-tight">
              Scorecard Name
            </Label>
            <Input
              id="scorecardName"
              value={options.scorecardName}
              onChange={(e) => setOptions({ ...options, scorecardName: e.target.value })}
              className="min-w-0 font-mono bg-background border-0"
              tabIndex={-1}
            />
          </div>

          <div className="grid grid-cols-[9rem_minmax(0,1fr)] items-center gap-4">
            <Label htmlFor="scoreName" className="text-right leading-tight">
              Score Name
            </Label>
            <Input
              id="scoreName"
              value={options.scoreName}
              onChange={(e) => setOptions({ ...options, scoreName: e.target.value })}
              className="min-w-0 font-mono bg-background border-0"
              tabIndex={-1}
            />
          </div>

          {options.versionId && (
            <div className="grid grid-cols-[9rem_minmax(0,1fr)] items-center gap-4">
              <Label htmlFor="versionId" className="text-right leading-tight">
                Version ID
              </Label>
              <Input
                id="versionId"
                value={options.versionId}
                className="min-w-0 font-mono bg-background border-0"
                readOnly
                disabled
                tabIndex={-1}
              />
            </div>
          )}

          <div className="grid grid-cols-[9rem_minmax(0,1fr)] items-center gap-4">
            <Label htmlFor="numberOfSamples" className="text-right leading-tight">
              Number of Samples
            </Label>
            <div className="min-w-0">
              <SampleSizeInput
                value={options.numberOfSamples}
                onChange={(value) => setOptions({ ...options, numberOfSamples: value })}
                min={1}
                max={10000}
                className="border-0"
              />
            </div>
          </div>

          <p className="pl-[calc(9rem+1rem)] text-sm text-muted-foreground">
            Uses the latest managed dataset linked to this score.
          </p>

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

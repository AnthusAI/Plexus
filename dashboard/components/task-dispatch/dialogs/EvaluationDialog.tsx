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
  Switch,
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
  samplingMethod: 'random' | 'sequential'
  loadFresh: boolean
  randomSeed?: number
  visualize: boolean
  logToLanggraph: boolean
}

export function EvaluationDialog({ action, isOpen, onClose, onDispatch, initialOptions }: TaskDialogProps & { initialOptions?: Partial<EvaluationOptions> }) {
  const [options, setOptions] = useState<EvaluationOptions>({
    scorecardName: initialOptions?.scorecardName || 'termlifev1',
    scoreName: initialOptions?.scoreName || 'Assumptive Close',
    numberOfSamples: initialOptions?.numberOfSamples || 10,
    samplingMethod: initialOptions?.samplingMethod || 'random',
    loadFresh: initialOptions?.loadFresh || false,
    randomSeed: initialOptions?.randomSeed,
    visualize: initialOptions?.visualize || false,
    logToLanggraph: initialOptions?.logToLanggraph || false
  })

  const handleDispatch = () => {
    // Extract evaluation type from action name by removing "Evaluate " prefix and converting to lowercase
    const evaluationType = action.name.replace(/^Evaluate\s+/, '').toLowerCase() as EvaluationType
    const generator = commands.evaluation[evaluationType]
    
    if (!generator || generator.type !== 'complex') {
      console.error('Invalid evaluation type:', evaluationType)
      return
    }

    const command = generator.generate(options)
    console.log('Generated evaluation command:', command)
    onDispatch(command, action.target)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-card border-0" hideCloseButton>
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
        <div className="grid gap-6 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="scorecardName" className="text-right">
              Scorecard Name
            </Label>
            <Input
              id="scorecardName"
              value={options.scorecardName}
              onChange={(e) => setOptions({ ...options, scorecardName: e.target.value })}
              className="col-span-3 font-mono bg-background border-0"
              tabIndex={-1}
            />
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="scoreName" className="text-right">
              Score Name
            </Label>
            <Input
              id="scoreName"
              value={options.scoreName}
              onChange={(e) => setOptions({ ...options, scoreName: e.target.value })}
              className="col-span-3 font-mono bg-background border-0"
              tabIndex={-1}
            />
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="numberOfSamples" className="text-right">
              Number of Samples
            </Label>
            <div className="col-span-3">
              <SampleSizeInput
                value={options.numberOfSamples}
                onChange={(value) => setOptions({ ...options, numberOfSamples: value })}
                min={1}
                max={10000}
                className="border-0"
              />
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="loadFresh" className="text-right">
              Load Fresh Data
            </Label>
            <div className="col-span-3 flex items-center">
              <Switch
                id="loadFresh"
                checked={options.loadFresh}
                onCheckedChange={(checked) => setOptions({ ...options, loadFresh: checked })}
                tabIndex={-1}
              />
            </div>
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

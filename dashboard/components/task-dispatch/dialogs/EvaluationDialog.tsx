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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
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

export function EvaluationDialog({ action, isOpen, onClose, onDispatch }: TaskDialogProps) {
  const [options, setOptions] = useState<EvaluationOptions>({
    scorecardName: 'termlifev1',
    scoreName: 'Assumptive Close',
    numberOfSamples: 10,
    samplingMethod: 'random',
    loadFresh: false,
    visualize: false,
    logToLanggraph: false
  })

  const handleDispatch = () => {
    // Extract evaluation type from action name
    const evaluationType = action.name.toLowerCase() as EvaluationType
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
        <div className="absolute right-4 top-4">
          <CardButton
            icon={X}
            onClick={onClose}
            aria-label="Close"
          />
        </div>
        <DialogHeader>
          <DialogTitle>{action.name} Evaluation</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-4">
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
            <Label htmlFor="samplingMethod" className="text-right">
              Sampling Method
            </Label>
            <Select
              value={options.samplingMethod}
              onValueChange={(value: 'random' | 'sequential') => 
                setOptions({ ...options, samplingMethod: value })}
            >
              <SelectTrigger className="col-span-3 border-0 bg-background" tabIndex={-1}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="border-0 bg-background">
                <SelectItem value="random">Random</SelectItem>
                <SelectItem value="sequential">Sequential</SelectItem>
              </SelectContent>
            </Select>
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

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="visualize" className="text-right">
              Visualize
            </Label>
            <div className="col-span-3 flex items-center">
              <Switch
                id="visualize"
                checked={options.visualize}
                onCheckedChange={(checked) => setOptions({ ...options, visualize: checked })}
                tabIndex={-1}
              />
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="logToLanggraph" className="text-right">
              Log to Langgraph
            </Label>
            <div className="col-span-3 flex items-center">
              <Switch
                id="logToLanggraph"
                checked={options.logToLanggraph}
                onCheckedChange={(checked) => setOptions({ ...options, logToLanggraph: checked })}
                tabIndex={-1}
              />
            </div>
          </div>

          {options.samplingMethod === 'random' && (
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="randomSeed" className="text-right">
                Random Seed (Optional)
              </Label>
              <div className="col-span-3">
                <Input
                  type="number"
                  value={options.randomSeed || ''}
                  onChange={(e) => setOptions({ 
                    ...options, 
                    randomSeed: e.target.value ? parseInt(e.target.value) : undefined 
                  })}
                  className="font-mono bg-background border-0"
                  placeholder="Leave empty for random seed"
                  min={0}
                  tabIndex={-1}
                />
              </div>
            </div>
          )}
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
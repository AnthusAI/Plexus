"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { CardButton } from "@/components/CardButton"
import { X, TestTube } from "lucide-react"

interface TestItemDialogProps {
  isOpen: boolean
  onClose: () => void
  onTest: (scoreId: string) => void
  itemDisplayValue: string
  availableScores: Array<{
    id: string
    name: string
    sectionName: string
  }>
}

export function TestItemDialog({ 
  isOpen, 
  onClose, 
  onTest, 
  itemDisplayValue, 
  availableScores 
}: TestItemDialogProps) {
  const [selectedScoreId, setSelectedScoreId] = useState<string>("")

  const handleTest = () => {
    if (selectedScoreId) {
      onTest(selectedScoreId)
      onClose()
      setSelectedScoreId("")
    }
  }

  const handleClose = () => {
    onClose()
    setSelectedScoreId("")
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="bg-card border-0" hideCloseButton>
        <div className="absolute right-4 top-4">
          <CardButton
            icon={X}
            onClick={handleClose}
            aria-label="Close"
          />
        </div>
        <DialogHeader>
          <div className="flex items-center gap-2">
            <TestTube className="h-5 w-5" />
            <DialogTitle>Test Item</DialogTitle>
          </div>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="itemName" className="text-right">
              Example Item
            </Label>
            <div className="col-span-3 font-mono bg-background border border-input rounded-md px-3 py-2 text-sm">
              {itemDisplayValue}
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="score" className="text-right">
              Score
            </Label>
            <Select
              value={selectedScoreId}
              onValueChange={setSelectedScoreId}
            >
              <SelectTrigger className="col-span-3 border-0 bg-background">
                <SelectValue placeholder="Select a score to test with" />
              </SelectTrigger>
              <SelectContent className="border-0 bg-background">
                {availableScores.map((score) => (
                  <SelectItem key={score.id} value={score.id}>
                    <div className="flex flex-col">
                      <span>{score.name}</span>
                      {score.sectionName && 
                       score.sectionName.toLowerCase() !== 'default' && 
                       score.sectionName.toLowerCase() !== 'untitled' && (
                        <span className="text-xs text-muted-foreground">{score.sectionName}</span>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={handleClose} className="bg-border border-0">
            Cancel
          </Button>
          <Button 
            onClick={handleTest} 
            className="border-0"
            disabled={!selectedScoreId}
          >
            Run Test
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
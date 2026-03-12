"use client"

import React, { useState } from "react"
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

interface TestScoreDialogProps {
  isOpen: boolean
  onClose: () => void
  onTest: (itemId: string) => void
  scoreName: string
  exampleItems: Array<{
    id: string
    displayValue: string
  }>
}

export function TestScoreDialog({ 
  isOpen, 
  onClose, 
  onTest, 
  scoreName, 
  exampleItems 
}: TestScoreDialogProps) {
  const [selectedItemId, setSelectedItemId] = useState<string>("")

  const handleTest = () => {
    if (selectedItemId) {
      onTest(selectedItemId)
      onClose()
      setSelectedItemId("")
    }
  }

  const handleClose = () => {
    onClose()
    setSelectedItemId("")
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
            <DialogTitle>Test Score</DialogTitle>
          </div>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="scoreName" className="text-right">
              Score
            </Label>
            <div className="col-span-3 font-mono bg-background border border-input rounded-md px-3 py-2 text-sm">
              {scoreName}
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="exampleItem" className="text-right">
              Example Item
            </Label>
            <Select
              value={selectedItemId}
              onValueChange={setSelectedItemId}
            >
              <SelectTrigger className="col-span-3 border-0 bg-background">
                <SelectValue placeholder="Select an example item to test" />
              </SelectTrigger>
              <SelectContent className="border-0 bg-background">
                {exampleItems.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.displayValue}
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
            disabled={!selectedItemId}
          >
            Run Test
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
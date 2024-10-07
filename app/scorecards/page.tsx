"use client"

import { useState } from "react"
import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { AudioLines, Siren, FileBarChart, FlaskConical, Zap, Plus, Pencil, Trash2, ArrowLeft, MoreHorizontal, Activity, ChevronDown, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const initialScorecards: Scorecard[] = [
  { id: "1", name: "SelectQuote Term Life v1", key: "SQTL1", scores: 10, viable: 8, scoreDetails: [] },
  { id: "2", name: "CS3 CRM Validation", key: "CS3CRM", scores: 15, viable: 12, scoreDetails: [] },
  { id: "3", name: "CS3 Services v2", key: "CS3SV2", scores: 8, viable: 7, scoreDetails: [] },
]

const scoreTypes = ["Numeric", "Percentage", "Boolean", "Text"]

// Define an interface for the scorecard structure
interface Scorecard {
  id: string;
  name: string;
  key: string;
  scores: number;
  viable: number;
  scoreDetails: Array<{ id: string; name: string; type: string }>;
}

export default function Scorecards() {
  const [scorecards, setScorecards] = useState<Scorecard[]>(initialScorecards)
  const [selectedScorecard, setSelectedScorecard] = useState<Scorecard | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editingScore, setEditingScore] = useState<{ id: string; name: string; type: string } | null>(null)

  const handleCreate = () => {
    setSelectedScorecard({
      id: "",
      name: "",
      key: "",
      scores: 0,
      viable: 0,
      scoreDetails: []
    });
    setIsEditing(true)
    setEditingScore(null) // Ensure we're not in score editing mode
  }

  const handleEdit = (scorecard: Scorecard) => {
    setSelectedScorecard({ ...scorecard })
    setIsEditing(true)
    setEditingScore(null)
  }

  const handleDelete = (id: string) => {
    setScorecards(scorecards.filter(scorecard => scorecard.id !== id))
    if (selectedScorecard && selectedScorecard.id === id) {
      setSelectedScorecard(null)
      setIsEditing(false)
    }
  }

  const handleSave = () => {
    if (selectedScorecard) {
      if (!selectedScorecard.id) {
        const newId = Date.now().toString()
        setScorecards([...scorecards, { ...selectedScorecard, id: newId }])
      } else {
        setScorecards(scorecards.map(scorecard => 
          scorecard.id === selectedScorecard.id ? selectedScorecard : scorecard
        ))
      }
      setIsEditing(false)
    }
  }

  const handleCancel = () => {
    setSelectedScorecard(null)
    setIsEditing(false)
    setEditingScore(null)
  }

  const handleAddScore = () => {
    setEditingScore({ id: "", name: "", type: "" })
  }

  const handleSaveScore = () => {
    if (selectedScorecard && editingScore) {
      if (!editingScore.id) {
        const newScore = { ...editingScore, id: Date.now().toString() }
        setSelectedScorecard({
          ...selectedScorecard,
          scores: selectedScorecard.scores + 1,
          scoreDetails: [...(selectedScorecard.scoreDetails || []), newScore]
        })
      } else {
        setSelectedScorecard({
          ...selectedScorecard,
          scoreDetails: (selectedScorecard.scoreDetails || []).map(score => 
            score.id === editingScore.id ? editingScore : score
          )
        })
      }
      setEditingScore(null)
    }
  }

  const handleDeleteScore = (scoreId: string) => {
    if (selectedScorecard) {
      setSelectedScorecard({
        ...selectedScorecard,
        scores: selectedScorecard.scores - 1,
        scoreDetails: (selectedScorecard.scoreDetails || []).filter(score => score.id !== scoreId)
      })
    }
  }

  const renderContent = () => {
    if (!selectedScorecard) {
      return (
        <>
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-3xl font-bold">Scorecards</h1>
              <p className="text-muted-foreground">
                Manage your scorecards and their associated scores.
              </p>
            </div>
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4" /> Create Scorecard
            </Button>
          </div>
          <div className="w-full overflow-x-auto">
            <Table className="w-full">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40%]">Name</TableHead>
                  <TableHead className="w-[15%]">Scores</TableHead>
                  <TableHead className="w-[15%]">Viable</TableHead>
                  <TableHead className="w-[30%]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scorecards.map((scorecard) => (
                  <TableRow key={scorecard.id}>
                    <TableCell className="w-[40%]">
                      <div className="cursor-pointer" onClick={() => handleEdit(scorecard)}>
                        <div className="font-medium">{scorecard.name}</div>
                        <div className="text-sm text-muted-foreground">{scorecard.id} - {scorecard.key}</div>
                      </div>
                    </TableCell>
                    <TableCell className="w-[15%]">{scorecard.scores}</TableCell>
                    <TableCell className="w-[15%]">{scorecard.viable}</TableCell>
                    <TableCell className="w-[30%]">
                      <div className="flex items-center space-x-2">
                        <Button variant="outline" size="sm" onClick={() => handleEdit(scorecard)}>
                          <Pencil className="h-4 w-4 mr-2" /> Edit
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleDelete(scorecard.id)}>
                          <Trash2 className="h-4 w-4 mr-2" /> Delete
                        </Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm">
                              <MoreHorizontal className="h-4 w-4 mr-2" /> More
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent>
                            <DropdownMenuItem>
                              <Activity className="h-4 w-4 mr-2" /> Activity
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <AudioLines className="h-4 w-4 mr-2" /> Items
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Siren className="h-4 w-4 mr-2" /> Alerts
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <FileBarChart className="h-4 w-4 mr-2" /> Reports
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <FlaskConical className="h-4 w-4 mr-2" /> Experiments
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Zap className="h-4 w-4 mr-2" /> Optimizations
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )
    } else if (!editingScore) {
      return (
        <div className="flex flex-col h-full">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCancel}
                className="mr-2"
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <h1 className="text-2xl font-bold">
                {selectedScorecard.name || "New Scorecard"}
              </h1>
            </div>
            {selectedScorecard.id && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline">
                    Actions <ChevronDown className="ml-2 h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem>
                    <Activity className="h-4 w-4 mr-2" /> Activity
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <AudioLines className="h-4 w-4 mr-2" /> Items
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <Siren className="h-4 w-4 mr-2" /> Alerts
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <FileBarChart className="h-4 w-4 mr-2" /> Reports
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <FlaskConical className="h-4 w-4 mr-2" /> Experiments
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <Zap className="h-4 w-4 mr-2" /> Optimizations
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
          <ScrollArea className="flex-grow">
            <div className="space-y-6 p-4">
              <div>
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={selectedScorecard.name}
                  onChange={(e) => setSelectedScorecard({ ...selectedScorecard, name: e.target.value })}
                  disabled={!isEditing}
                />
              </div>
              <div>
                <Label htmlFor="key">Key</Label>
                <Input
                  id="key"
                  value={selectedScorecard.key}
                  onChange={(e) => setSelectedScorecard({ ...selectedScorecard, key: e.target.value })}
                  disabled={!isEditing}
                />
              </div>
              <div>
                <Label htmlFor="id">ID</Label>
                <Input
                  id="id"
                  value={selectedScorecard.id}
                  onChange={(e) => setSelectedScorecard({ ...selectedScorecard, id: e.target.value })}
                  disabled={true}
                />
              </div>
              <div>
                <div className="flex justify-between items-center mb-2">
                  <h2 className="text-xl font-semibold">Scores</h2>
                  <Button onClick={handleAddScore}>
                    <Plus className="mr-2 h-4 w-4" /> Add Score
                  </Button>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(selectedScorecard.scoreDetails || []).map((score) => (
                      <TableRow key={score.id}>
                        <TableCell>{score.name}</TableCell>
                        <TableCell>{score.type}</TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <Button variant="outline" size="sm" onClick={() => setEditingScore(score)}>
                              <Pencil className="h-4 w-4 mr-2" /> Edit
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => handleDeleteScore(score.id)}>
                              <Trash2 className="h-4 w-4 mr-2" /> Delete
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </ScrollArea>
          <div className="flex justify-end space-x-2 p-4 bg-gray-100">
            {isEditing ? (
              <>
                <Button onClick={handleSave}>Save Scorecard</Button>
                <Button variant="outline" onClick={handleCancel}>Cancel</Button>
              </>
            ) : (
              <>
                <Button onClick={() => setIsEditing(true)}>Edit Scorecard</Button>
                <Button variant="outline" onClick={handleCancel}>Close</Button>
              </>
            )}
          </div>
        </div>
      )
    } else {
      return (
        <div className="flex flex-col h-full">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditingScore(null)}
                className="mr-2"
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <h1 className="text-2xl font-bold">
                {editingScore.id ? `Edit Score: ${editingScore.name}` : "Add New Score"}
              </h1>
            </div>
          </div>
          <ScrollArea className="flex-grow">
            <div className="space-y-6 p-4">
              <div>
                <Label htmlFor="scoreName">Score Name</Label>
                <Input
                  id="scoreName"
                  value={editingScore.name}
                  onChange={(e) => setEditingScore({ ...editingScore, name: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="scoreType">Score Type</Label>
                <Select
                  value={editingScore.type}
                  onValueChange={(value) => setEditingScore({ ...editingScore, type: value })}
                >
                  <SelectTrigger id="scoreType">
                    <SelectValue placeholder="Select score type" />
                  </SelectTrigger>
                  <SelectContent>
                    {scoreTypes.map((type) => (
                      <SelectItem key={type} value={type}>{type}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </ScrollArea>
          <div className="flex justify-end space-x-2 p-4 bg-gray-100">
            <Button onClick={handleSaveScore}>Save Score</Button>
            <Button variant="outline" onClick={() => setEditingScore(null)}>Cancel</Button>
          </div>
        </div>
      )
    }
  }

  return (
    <DashboardLayout signOut={signOut}>
      <div className="p-6 space-y-6">
        {renderContent()}
      </div>
    </DashboardLayout>
  )
}
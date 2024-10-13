"use client"

import { useState, useRef, useEffect } from "react"
import { AudioLines, Siren, FileBarChart, FlaskConical, Zap, Plus, Pencil, Trash2, ArrowLeft, MoreHorizontal, Activity, ChevronDown, Square, Columns2, X } from "lucide-react"
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
import { Card, CardHeader, CardContent } from "@/components/ui/card"

const initialScorecards: Scorecard[] = [
  { id: "1", name: "SelectQuote Term Life v1", key: "SQTL1", scores: 10, scoreDetails: [] },
  { id: "2", name: "CS3 CRM Validation", key: "CS3CRM", scores: 15, scoreDetails: [] },
  { id: "3", name: "CS3 Services v2", key: "CS3SV2", scores: 8, scoreDetails: [] },
]

const scoreTypes = ["Numeric", "Percentage", "Boolean", "Text"]

// Define an interface for the scorecard structure
interface Scorecard {
  id: string;
  name: string;
  key: string;
  scores: number;
  scoreDetails: Array<{ id: string; name: string; type: string }>;
}

type EditableFieldProps = {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

function EditableField({ value, onChange, className = "" }: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isEditing])

  const handleEditToggle = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsEditing((prev) => !prev);
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value)
  }

  const handleInputBlur = () => {
    setTimeout(() => {
      setIsEditing(false);
    }, 100);
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      setIsEditing(false)
    }
  }

  return (
    <div className="flex items-center space-x-2">
      {isEditing ? (
        <Input
          ref={inputRef}
          type="text"
          value={value}
          onChange={handleInputChange}
          onBlur={handleInputBlur}
          onKeyDown={handleKeyDown}
          className={`py-1 px-2 ${className}`}
        />
      ) : (
        <span 
          className={`cursor-pointer hover:bg-gray-100 py-1 px-2 rounded transition-colors duration-200 ${className}`}
          onClick={handleEditToggle}
        >
          {value}
        </span>
      )}
      <Button 
        variant="outline" 
        size="sm" 
        onMouseDown={handleEditToggle}
      >
        {isEditing ? 'Save' : 'Edit'}
      </Button>
    </div>
  )
}

export default function ScorecardsComponent() {
  const [scorecards, setScorecards] = useState<Scorecard[]>(initialScorecards)
  const [selectedScorecard, setSelectedScorecard] = useState<Scorecard | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editingScore, setEditingScore] = useState<{ id: string; name: string; type: string } | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)

  const handleCreate = () => {
    const newScorecard: Scorecard = {
      id: "",
      name: "",
      key: "",
      scores: 0,
      scoreDetails: []
    }
    setSelectedScorecard(newScorecard)
    setIsEditing(true)
    setEditingScore(null)
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

  const renderScorecardsTable = () => (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[50%]">Scorecard</TableHead>
          <TableHead className="w-[20%] text-right">Scores</TableHead>
          <TableHead className="w-[30%] text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {scorecards.map((scorecard) => (
          <TableRow key={scorecard.id} onClick={() => setSelectedScorecard(scorecard)} className="cursor-pointer">
            <TableCell className="w-[50%]">
              <div>
                <div className="font-medium">{scorecard.name}</div>
                <div className="text-sm text-muted-foreground">{scorecard.id} - {scorecard.key}</div>
              </div>
            </TableCell>
            <TableCell className="w-[20%] text-right">{scorecard.scores}</TableCell>
            <TableCell className="w-[30%]">
              <div className="flex items-center justify-end space-x-2">
                <Button variant="outline" size="sm" className="border border-secondary" onClick={(e) => { e.stopPropagation(); handleEdit(scorecard); }}>
                  <Pencil className="h-4 w-4 mr-2" /> Edit
                </Button>
                <Button variant="outline" size="sm" className="border border-secondary" onClick={(e) => { e.stopPropagation(); handleDelete(scorecard.id); }}>
                  <Trash2 className="h-4 w-4 mr-2" /> Delete
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="border border-secondary" onClick={(e) => e.stopPropagation()}>
                      <MoreHorizontal className="h-4 w-4 mr-2" /> More
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
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
  )

  const renderSelectedScorecard = () => (
    <Card className="rounded-none sm:rounded-lg flex flex-col h-full">
      <CardHeader className="py-4 px-4 sm:px-6 flex-shrink-0">
        <div className="flex flex-col space-y-4 w-full">
          <div className="flex justify-between items-start">
            <EditableField 
              value={selectedScorecard?.name || "New Scorecard"} 
              onChange={(value) => setSelectedScorecard(prev => prev ? { ...prev, name: value } : null)}
              className="text-2xl font-bold"
            />
            <div className="flex space-x-2">
              {!isNarrowViewport && (
                <Button variant="outline" size="icon" onClick={() => setIsFullWidth(!isFullWidth)}>
                  {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                </Button>
              )}
              <Button variant="outline" size="icon" onClick={() => {
                setSelectedScorecard(null)
                setIsFullWidth(false)
              }}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="flex justify-between">
            <EditableField 
              value={selectedScorecard?.key || "Key"} 
              onChange={(value) => setSelectedScorecard(prev => prev ? { ...prev, key: value } : null)}
              className="font-mono"
            />
            <EditableField 
              value={selectedScorecard?.id || "ID"} 
              onChange={(value) => setSelectedScorecard(prev => prev ? { ...prev, id: value } : null)}
              className="font-mono"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-grow overflow-auto px-4 sm:px-6">
        <ScrollArea className="h-full">
          <div className="space-y-6">
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
                  {(selectedScorecard?.scoreDetails || []).map((score) => (
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
      </CardContent>
    </Card>
  )

  return (
    <div className="space-y-6 h-full flex flex-col">
      <div className="flex justify-end">
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" /> Create Scorecard
        </Button>
      </div>

      <div className={`flex flex-col flex-grow overflow-hidden ${isNarrowViewport || isFullWidth ? 'space-y-6' : 'space-x-6'}`}>
        {selectedScorecard && (isNarrowViewport || isFullWidth) && (
          <div className="flex-shrink-0">
            {renderSelectedScorecard()}
          </div>
        )}
        
        <div className={`flex ${isNarrowViewport || isFullWidth ? 'flex-col' : 'space-x-6'} h-full overflow-hidden`}>
          <div className={`${isFullWidth && selectedScorecard ? 'hidden' : 'flex-1'} overflow-auto`}>
            {renderScorecardsTable()}
          </div>

          {selectedScorecard && !isNarrowViewport && !isFullWidth && (
            <div className="flex-1 overflow-hidden">
              {renderSelectedScorecard()}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
"use client"
import React, { useState, useRef, useEffect } from "react"
import { AudioLines, Siren, FileBarChart, FlaskConical, Zap, Plus, Pencil, Trash2, ArrowLeft, MoreHorizontal, Activity, ChevronDown, Square, Columns2, X, Search, Check, Info, ThumbsUp, ThumbsDown, MessageCircleMore } from "lucide-react"
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
import { format, formatDistanceToNow } from "date-fns"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { PieChart, Pie, ResponsiveContainer, Cell } from "recharts"
import { Badge } from "@/components/ui/badge"
import Link from 'next/link'

const initialScorecards: Scorecard[] = [
  { 
    id: "1329", 
    name: "SelectQuote Term Life v1", 
    key: "termlifev1", 
    scores: 12, 
    scoreDetails: [
      {
        name: "Technical",
        scores: [
          { 
            id: "1", 
            name: "Scoreable Call", 
            type: "Boolean",
            accuracy: 85,
            version: "a1b2c3d",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 85 },
              { category: "Negative", value: 15 }
            ],
            versionHistory: []
          },
          { 
            id: "2", 
            name: "Call Efficiency", 
            type: "Boolean",
            accuracy: 78,
            version: "e4f5g6h",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 78 },
              { category: "Negative", value: 22 }
            ],
            versionHistory: []
          },
        ]
      },
      {
        name: "Sales",
        scores: [
          { 
            id: "3", 
            name: "Assumptive Close", 
            type: "Boolean",
            accuracy: 94,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "4", 
            name: "Problem Resolution", 
            type: "Boolean",
            accuracy: 92,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
        ]
      },
      {
        name: "Soft Skills",
        scores: [
          { 
            id: "5", 
            name: "Rapport", 
            type: "Boolean",
            accuracy: 94,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "6", 
            name: "Friendly Greeting", 
            type: "Boolean",
            accuracy: 89,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "7", 
            name: "Agent Offered Name", 
            type: "Boolean",
            accuracy: 98,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "8", 
            name: "Temperature Check", 
            type: "Boolean",
            accuracy: 91,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
        ]
      },
      {
        name: "Compliance",
        scores: [
          { 
            id: "9", 
            name: "DNC Requested", 
            type: "Boolean",
            accuracy: 98,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "10", 
            name: "Profanity", 
            type: "Boolean",
            accuracy: 99,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "11", 
            name: "Agent Offered Legal Advice", 
            type: "Boolean",
            accuracy: 97,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
          { 
            id: "12", 
            name: "Agent Offered Guarantees", 
            type: "Boolean",
            accuracy: 98,
            version: "initial",
            timestamp: new Date(),
            distribution: [
              { category: "Positive", value: 0 },
              { category: "Negative", value: 0 }
            ],
            versionHistory: []
          },
        ]
      }
    ]
  },
  { id: "1321", name: "CS3 Audigy TPA", key: "cs3_audigy_tpa", scores: 1, scoreDetails: [] },
  { id: "1372", name: "CS3 Services v2", key: "cs3_services_v2", scores: 1, scoreDetails: [] },
]

const scoreTypes = ["Numeric", "Percentage", "Boolean", "Text"]

// Define an interface for the scorecard structure
interface Scorecard {
  id: string;
  name: string;
  key: string;
  scores: number;
  scoreDetails: Array<{
    name: string;
    scores: Array<{
      id: string;
      name: string;
      type: string;
      accuracy: number;
      version: string;
      timestamp: Date;
      distribution: Array<{ category: string; value: number }>;
      versionHistory: Array<{
        version: string;
        timestamp: Date;
        accuracy: number;
        distribution: Array<{ category: string; value: number }>;
      }>;
      aiProvider?: string;
      aiModel?: string;
      isFineTuned?: boolean;
    }>;
  }>;
}

type EditableFieldProps = {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  autoFocus?: boolean;
}

function EditableField({ value, onChange, className = "", autoFocus = false }: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(autoFocus)
  const [tempValue, setTempValue] = useState(value)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if ((isEditing || autoFocus) && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isEditing, autoFocus])

  const handleEditToggle = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsEditing((prev) => !prev);
    setTempValue(value);
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTempValue(e.target.value)
  }

  const handleSave = () => {
    onChange(tempValue)
    setIsEditing(false)
  }

  const handleCancel = () => {
    setTempValue(value)
    setIsEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSave()
    } else if (e.key === 'Escape') {
      handleCancel()
    }
  }

  return (
    <div className="flex items-center space-x-2">
      {isEditing ? (
        <>
          <Input
            ref={inputRef}
            type="text"
            value={tempValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            className={`py-1 px-2 -ml-2 ${className}`}
          />
          <Button 
            variant="ghost" 
            size="icon"
            className="h-8 w-8 flex-shrink-0"
            onClick={handleSave}
          >
            <Check className="h-4 w-4" />
          </Button>
          <Button 
            variant="ghost" 
            size="icon"
            className="h-8 w-8 flex-shrink-0"
            onClick={handleCancel}
          >
            <X className="h-4 w-4" />
          </Button>
        </>
      ) : (
        <>
          <span 
            className={`cursor-pointer hover:bg-accent hover:text-accent-foreground py-1 px-2 -ml-2 rounded border border-transparent transition-colors duration-200 ${className}`}
          >
            {value}
          </span>
          <Button 
            variant="ghost" 
            size="icon"
            className="h-8 w-8 flex-shrink-0"
            onClick={handleEditToggle}
          >
            <Pencil className="h-4 w-4" />
          </Button>
        </>
      )}
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
  const [editingName, setEditingName] = useState(false)
  const [isDetailViewFresh, setIsDetailViewFresh] = useState(true)

  // Move useEffect to the top level
  useEffect(() => {
    if (isDetailViewFresh && selectedScorecard) {
      setIsDetailViewFresh(false);
    }
  }, [isDetailViewFresh, selectedScorecard]);

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
    setIsDetailViewFresh(true)
  }

  const handleEdit = (scorecard: Scorecard) => {
    setSelectedScorecard({ ...scorecard })
    setIsEditing(true)
    setEditingScore(null)
    setIsDetailViewFresh(true)
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

  const handleAddScore = (sectionIndex: number) => {
    const baseAccuracy = Math.floor(Math.random() * 30) + 60; // Random accuracy between 60% and 90%
    const newScore = { 
      id: Date.now().toString(), 
      name: "New Score", 
      type: "Boolean",
      accuracy: baseAccuracy,
      version: generateHexCode(),
      timestamp: new Date(),
      distribution: [
        { category: "Positive", value: baseAccuracy },
        { category: "Negative", value: 100 - baseAccuracy }
      ],
      versionHistory: []
    };
    const updatedScoreDetails = [...selectedScorecard.scoreDetails];
    updatedScoreDetails[sectionIndex].scores.push(newScore);
    setSelectedScorecard({
      ...selectedScorecard,
      scoreDetails: updatedScoreDetails,
      scores: selectedScorecard.scores + 1
    });
  };

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

  const handleNameEdit = () => {
    setEditingName(true)
  }

  const handleNameSave = (newName: string) => {
    if (selectedScorecard) {
      setSelectedScorecard({ ...selectedScorecard, name: newName })
      setEditingName(false)
    }
  }

  const renderScorecardsTable = () => (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[70%]">Scorecard</TableHead>
            <TableHead className="w-[20%] text-right">Scores</TableHead>
            <TableHead className="w-[10%] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {scorecards.map((scorecard) => (
            <TableRow 
              key={scorecard.id} 
              onClick={() => setSelectedScorecard(scorecard)} 
              className="cursor-pointer transition-colors duration-200 hover:bg-muted"
            >
              <TableCell className="w-[70%]">
                <div>
                  <div className="font-medium">{scorecard.name}</div>
                  <div className="text-sm text-muted-foreground">{scorecard.id} - {scorecard.key}</div>
                </div>
              </TableCell>
              <TableCell className="w-[20%] text-right">{scorecard.scores}</TableCell>
              <TableCell className="w-[10%]">
                <div className="flex items-center justify-end space-x-2">
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={(e) => { e.stopPropagation(); handleEdit(scorecard); }}
                    className="h-8 w-8 p-0"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={(e) => e.stopPropagation()}
                        className="h-8 w-8 p-0"
                      >
                        <MoreHorizontal className="h-4 w-4" />
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
      <div className="mt-4">
        <Button variant="outline" onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" /> Create Scorecard
        </Button>
      </div>
    </div>
  )

  const renderSelectedItem = () => {
    if (!selectedScorecard) return null;

    const handleAddSection = () => {
      const newSection = {
        name: "New section",
        scores: []
      };
      setSelectedScorecard({
        ...selectedScorecard,
        scoreDetails: [...selectedScorecard.scoreDetails, newSection]
      });
    };

    const renderScoreItem = (score: Scorecard['scoreDetails'][0]['scores'][0]) => {
      const generateVersionHistory = (baseAccuracy: number) => {
        const now = new Date();
        return [
          {
            version: generateHexCode(),
            parent: generateHexCode(),
            timestamp: new Date(now.getTime() - 2 * 60 * 60 * 1000), // 2 hours ago
            accuracy: baseAccuracy,
            distribution: [{ category: "Positive", value: baseAccuracy }, { category: "Negative", value: 100 - baseAccuracy }]
          },
          {
            version: generateHexCode(),
            parent: generateHexCode(),
            timestamp: new Date(now.getTime() - 1 * 24 * 60 * 60 * 1000), // 1 day ago
            accuracy: baseAccuracy - 3,
            distribution: [{ category: "Positive", value: baseAccuracy - 3 }, { category: "Negative", value: 103 - baseAccuracy }]
          },
          {
            version: generateHexCode(),
            parent: generateHexCode(),
            timestamp: new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000), // 3 days ago
            accuracy: baseAccuracy - 7,
            distribution: [{ category: "Positive", value: baseAccuracy - 7 }, { category: "Negative", value: 107 - baseAccuracy }]
          },
          {
            version: generateHexCode(),
            parent: null,
            timestamp: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000), // 7 days ago
            accuracy: baseAccuracy - 12,
            distribution: [{ category: "Positive", value: baseAccuracy - 12 }, { category: "Negative", value: 112 - baseAccuracy }]
          },
        ];
      };

      if (!score.versionHistory || score.versionHistory.length === 0) {
        score.versionHistory = generateVersionHistory(score.accuracy);
      }

      const latestVersion = score.versionHistory[0];
      const totalItems = latestVersion.distribution.reduce((sum, item) => sum + item.value, 0);

      return (
        <div key={score.id} className="py-4 border-b last:border-b-0">
          <div className="flex justify-between items-start mb-1">
            <div className="flex flex-col">
              <h5 className="text-sm font-medium">{score.name}</h5>
              <div className="text-xs text-muted-foreground mt-1 space-y-1">
                <div className="font-mono">LangGraphScore</div>
                <div className="flex flex-wrap gap-1">
                  <Badge className="bg-muted-foreground text-muted">{score.aiProvider || 'OpenAI'}</Badge>
                  <Badge className="bg-muted-foreground text-muted">{score.aiModel || 'gpt-4o-mini'}</Badge>
                  {score.isFineTuned && <Badge variant="secondary">Fine-tuned</Badge>}
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="text-xs">
                    <Search className="h-4 w-4 mr-1" />
                    Find
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
              <Button variant="outline" size="sm" className="text-xs">
                <Pencil className="h-4 w-4 mr-1" />
                Edit
              </Button>
            </div>
          </div>
          <div className="flex items-center justify-end mt-2">
            <div className="text-right mr-4">
              <div className="text-lg font-bold">
                {latestVersion.accuracy}% / {totalItems}
              </div>
              <div className="text-sm text-muted-foreground">
                Accuracy
              </div>
            </div>
            <div className="w-[80px] h-[80px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={latestVersion.distribution}
                    dataKey="value"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    innerRadius={0}
                    outerRadius={30}
                    fill="var(--true)"
                    strokeWidth={0}
                  >
                    {latestVersion.distribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={index === 0 ? "var(--true)" : "var(--false)"} />
                    ))}
                  </Pie>
                  <Pie
                    data={[
                      { category: "Positive", value: 50 },
                      { category: "Negative", value: 50 },
                    ]}
                    dataKey="value"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    innerRadius={35}
                    outerRadius={40}
                    fill="var(--chart-2)"
                    strokeWidth={0}
                  >
                    {[0, 1].map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={index === 0 ? "var(--true)" : "var(--false)"} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <Collapsible className="w-full mt-2">
            <CollapsibleTrigger className="flex items-center text-sm text-muted-foreground">
              <span>Version History</span>
              <ChevronDown className="h-4 w-4 ml-1" />
            </CollapsibleTrigger>
            <CollapsibleContent className="border-l-4 border-primary pl-4 mt-2">
              <div className="max-h-80 overflow-y-auto pr-4">
                <div className="space-y-4">
                  {score.versionHistory.map((version, index) => (
                    <div key={index} className="border-b last:border-b-0 pb-4">
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="text-sm font-medium">
                            Version {version.version.substring(0, 7)}
                            {index === 0 && (
                              <span className="ml-2 text-xs bg-secondary text-secondary-foreground px-2 py-1 rounded-full">
                                Current
                              </span>
                            )}
                          </div>
                          {version.parent && (
                            <div className="text-xs text-muted-foreground">
                              Parent: <a href="#" className="text-primary hover:underline" onClick={(e) => {
                                e.preventDefault();
                                console.log(`Navigate to parent version: ${version.parent}`);
                              }}>{version.parent.substring(0, 7)}</a>
                            </div>
                          )}
                          <div className="text-xs text-muted-foreground">
                            {formatDistanceToNow(version.timestamp, { addSuffix: true })}
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          {index !== 0 && (
                            <Button variant="outline" size="sm">Use</Button>
                          )}
                          <Button variant="outline" size="sm">Edit</Button>
                        </div>
                      </div>
                      <div className="flex items-center justify-end mt-2">
                        <div className="text-right mr-4">
                          <div className="text-lg font-bold">
                            {version.accuracy}% / {version.distribution.reduce((sum, item) => sum + item.value, 0)}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            Accuracy
                          </div>
                        </div>
                        <div className="w-[60px] h-[60px]">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={version.distribution}
                                dataKey="value"
                                nameKey="category"
                                cx="50%"
                                cy="50%"
                                innerRadius={0}
                                outerRadius={25}
                                fill="var(--true)"
                                strokeWidth={0}
                              >
                                {version.distribution.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={index === 0 ? "var(--true)" : "var(--false)"} />
                                ))}
                              </Pie>
                              <Pie
                                data={[
                                  { category: "Positive", value: 50 },
                                  { category: "Negative", value: 50 },
                                ]}
                                dataKey="value"
                                nameKey="category"
                                cx="50%"
                                cy="50%"
                                innerRadius={27}
                                outerRadius={30}
                                fill="var(--chart-2)"
                                strokeWidth={0}
                              >
                                {[0, 1].map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={index === 0 ? "var(--true)" : "var(--false)"} />
                                ))}
                              </Pie>
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      );
    };

    // Helper function to generate a random hex code
    const generateHexCode = () => {
      return Math.random().toString(16).substr(2, 7);
    };

    return (
      <Card className="rounded-none sm:rounded-lg h-full flex flex-col">
        <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between py-4 px-4 sm:px-6 space-y-0">
          <div className="flex-grow">
            <EditableField
              value={selectedScorecard.name}
              onChange={(value) => setSelectedScorecard({ ...selectedScorecard, name: value })}
              className="text-xl font-semibold"
            />
          </div>
          <div className="flex ml-2">
            {!isNarrowViewport && (
              <Button variant="outline" size="icon" onClick={() => setIsFullWidth(!isFullWidth)}>
                {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
              </Button>
            )}
            <Button variant="outline" size="icon" onClick={() => {
              setSelectedScorecard(null);
              setIsFullWidth(false);
              setIsDetailViewFresh(true);
            }} className="ml-2">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex-grow overflow-auto px-4 sm:px-6 pb-4">
          <div className="space-y-4">
            <div className="flex justify-between">
              <EditableField 
                value={selectedScorecard.key} 
                onChange={(value) => setSelectedScorecard({ ...selectedScorecard, key: value })}
                className="font-mono"
              />
              <EditableField 
                value={selectedScorecard.id} 
                onChange={(value) => setSelectedScorecard({ ...selectedScorecard, id: value })}
                className="font-mono"
              />
            </div>
            
            <div className="mt-8">
              <div className="-mx-4 sm:-mx-6 mb-4">
                <div className="px-4 sm:px-6 py-2">
                  <h4 className="text-md font-semibold">Scores</h4>
                </div>
              </div>
              {selectedScorecard.scoreDetails.map((section, sectionIndex) => (
                <div key={sectionIndex} className="mb-6">
                  <div className="-mx-4 sm:-mx-6 mb-4">
                    <div className="bg-muted px-4 sm:px-6 py-2">
                      <EditableField
                        value={section.name}
                        onChange={(value) => {
                          const updatedScoreDetails = [...selectedScorecard.scoreDetails];
                          updatedScoreDetails[sectionIndex] = { ...section, name: value };
                          setSelectedScorecard({ ...selectedScorecard, scoreDetails: updatedScoreDetails });
                        }}
                        className="text-md font-semibold"
                      />
                    </div>
                  </div>
                  <div>
                    {section.scores.map((score) => renderScoreItem(score))}
                  </div>
                  <div className="mt-4">
                    <Button variant="outline" onClick={() => handleAddScore(sectionIndex)}>
                      <Plus className="mr-2 h-4 w-4" /> Create Score
                    </Button>
                  </div>
                </div>
              ))}
              <div className="mt-6">
                <Button variant="outline" onClick={handleAddSection}>
                  <Plus className="mr-2 h-4 w-4" /> Create Section
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className={`flex flex-col flex-grow overflow-hidden pb-2`}>
        {selectedScorecard && (isNarrowViewport || isFullWidth) && (
          <div className="flex-shrink-0 h-full overflow-hidden">
            {renderSelectedItem()}
          </div>
        )}
        
        <div className={`flex ${isNarrowViewport || isFullWidth ? 'flex-col' : 'space-x-6'} h-full overflow-hidden`}>
          <div className={`${isFullWidth && selectedScorecard ? 'hidden' : 'flex-1'} overflow-auto`}>
            {renderScorecardsTable()}
          </div>

          {selectedScorecard && !isNarrowViewport && !isFullWidth && (
            <div className="flex-1 overflow-hidden">
              {renderSelectedItem()}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
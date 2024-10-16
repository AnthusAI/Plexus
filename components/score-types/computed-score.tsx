import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Plus, Trash } from 'lucide-react'

interface ComputedScoreProps {
  score: any
  onChange: (score: any) => void
}

interface PredicateRule {
  id: string
  scoreName: string
  operator: string
  value: string
  action: string
  points: number
}

const sampleScoreNames = [
  "Scoreable Call",
  "Call Efficiency",
  "Assumptive Close",
  "Problem Resolution",
  "Rapport",
  "Friendly Greeting",
  "Agent Offered Name",
  "Temperature Check",
  "DNC Requested",
  "Profanity",
  "Agent Offered Legal Advice",
  "Agent Offered Guarantees"
]

const operators = ["=", "!="]
const actions = ["deduct", "add"]

const initialRules: PredicateRule[] = [
  { id: "1", scoreName: "Call Efficiency", operator: "!=", value: "true", action: "deduct", points: 1 },
  { id: "2", scoreName: "Rapport", operator: "!=", value: "true", action: "deduct", points: 2 },
  { id: "3", scoreName: "Profanity", operator: "=", value: "true", action: "deduct", points: 5 },
]

export default function ComputedScoreComponent({ score, onChange }: ComputedScoreProps) {
  const [startingTotal, setStartingTotal] = useState(score.startingTotal || 100)
  const [rules, setRules] = useState<PredicateRule[]>(score.rules || initialRules)

  useEffect(() => {
    onChange({ ...score, startingTotal, rules })
  }, [startingTotal, rules])

  const addRule = () => {
    const newRule: PredicateRule = {
      id: Date.now().toString(),
      scoreName: "",
      operator: "=",
      value: "true",
      action: "deduct",
      points: 1
    }
    setRules([...rules, newRule])
  }

  const updateRule = (id: string, field: keyof PredicateRule, value: string | number) => {
    const updatedRules = rules.map(rule =>
      rule.id === id ? { ...rule, [field]: value } : rule
    )
    setRules(updatedRules)
  }

  const removeRule = (id: string) => {
    const updatedRules = rules.filter(rule => rule.id !== id)
    setRules(updatedRules)
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="startingTotal">Starting Total</Label>
        <Input
          id="startingTotal"
          type="number"
          value={startingTotal}
          onChange={(e) => setStartingTotal(Number(e.target.value))}
          className="w-full"
        />
      </div>
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">Adjustment Rules</h3>
        {rules.map(rule => (
          <div key={rule.id} className="flex items-center space-x-2">
            <div className="w-[30%]">
              <Select
                value={rule.scoreName}
                onValueChange={(value) => updateRule(rule.id, 'scoreName', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select score" />
                </SelectTrigger>
                <SelectContent>
                  {sampleScoreNames.map(name => (
                    <SelectItem key={name} value={name}>{name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-[15%]">
              <Select
                value={rule.operator}
                onValueChange={(value) => updateRule(rule.id, 'operator', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Operator" />
                </SelectTrigger>
                <SelectContent>
                  {operators.map(op => (
                    <SelectItem key={op} value={op}>{op}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-[15%]">
              <Select
                value={rule.value}
                onValueChange={(value) => updateRule(rule.id, 'value', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Value" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">true</SelectItem>
                  <SelectItem value="false">false</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="w-[15%]">
              <Select
                value={rule.action}
                onValueChange={(value) => updateRule(rule.id, 'action', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Action" />
                </SelectTrigger>
                <SelectContent>
                  {actions.map(action => (
                    <SelectItem key={action} value={action}>{action}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-[15%]">
              <Input
                type="number"
                value={rule.points}
                onChange={(e) => updateRule(rule.id, 'points', Number(e.target.value))}
                placeholder="Points"
              />
            </div>
            <div className="w-[10%] flex justify-end">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeRule(rule.id)}
              >
                <Trash className="h-4 w-4" />
              </Button>
            </div>
          </div>
        ))}
      </div>
      <Button onClick={addRule} variant="outline" size="sm">
        <Plus className="h-4 w-4 mr-2" /> Add Rule
      </Button>
    </div>
  )
}

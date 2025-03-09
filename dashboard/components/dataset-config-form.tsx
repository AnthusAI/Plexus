"use client"

import { useState } from "react"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { HelpCircle, X, Square, Columns2 } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Textarea } from "@/components/ui/textarea"
import { ChevronDownIcon, ChevronUpIcon } from "@radix-ui/react-icons"
import { CardButton } from "@/components/CardButton"

interface DatasetConfigFormProps {
  scorecardId?: string
  onClose?: () => void
  isFullWidth?: boolean
  onToggleWidth?: () => void
  isNarrowViewport?: boolean
}

export function DatasetConfigFormComponent({
  scorecardId,
  onClose,
  isFullWidth = false,
  onToggleWidth,
  isNarrowViewport = false
}: DatasetConfigFormProps) {
  const [isQueryVisible, setIsQueryVisible] = useState(false)
  const [config, setConfig] = useState({
    max_number: 10000,
    balance_dataset: true,
    min_feedback: "",
    feedback_agreement: false,
    score_value: "",
    query: `SELECT {% if limit %}TOP {{limit}}{% endif %}
    a.f_id
FROM vwForm a
JOIN vwCF b ON a.SESSION_ID = b.SESSION_ID
{% if min_calibrations or require_matching_answers %}
JOIN (
  SELECT 
      vcf.f_id,
      COUNT(DISTINCT vcf.id) as calibration_count,
      {% if require_matching_answers %}
      MIN(CASE WHEN fqs.question_answered = cs.question_result THEN 1 ELSE 0 END) as all_answers_match
      {% endif %}
  FROM vwCalibrationForm vcf
  {% if require_matching_answers %}
  JOIN calibration_scores cs ON cs.form_id = vcf.id
  JOIN form_q_scores fqs ON fqs.form_id = vcf.f_id AND fqs.question_id = cs.question_id
  {% endif %}
  GROUP BY vcf.f_id
  HAVING 
      {% if min_calibrations %}COUNT(DISTINCT vcf.id) >= {{min_calibrations}}{% endif %}
      {% if min_calibrations and require_matching_answers %}AND{% endif %}
      {% if require_matching_answers %}MIN(CASE WHEN fqs.question_answered = cs.question_result THEN 1 ELSE 0 END) = 1{% endif %}
) cal_counts ON a.f_id = cal_counts.f_id
{% endif %}
WHERE 
  ISNULL(a.bad_call_reason, '') = ISNULL(b.bad_calibration_reason, '') 
  AND a.transcript_analyzed IS NOT NULL
  {% if score_value %}AND a.score = {{score_value}}{% endif %}`
  })

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target
    setConfig(prev => ({
      ...prev,
      [name]: type === "number" ? parseInt(value) || "" : value
    }))
  }

  const handleSwitchChange = (name: string) => (checked: boolean) => {
    setConfig(prev => ({ ...prev, [name]: checked }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    console.log("Submitted configuration:", config)
    // Here you would typically send the config to your backend or process it further
  }

  return (
    <div className="border text-card-foreground shadow rounded-lg h-full flex flex-col 
      bg-card-light border-none">
      <div className="flex-shrink-0 bg-card rounded-t-lg">
        <div className="px-6 py-4 flex items-center justify-between">
          <h2 className="text-3xl font-semibold">Dataset Configuration</h2>
          <div className="flex items-center space-x-2">
            {!isNarrowViewport && onToggleWidth && (
              <CardButton
                icon={isFullWidth ? Columns2 : Square}
                onClick={onToggleWidth}
              />
            )}
            {onClose && (
              <CardButton
                icon={X}
                onClick={() => onClose?.()}
              />
            )}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <form onSubmit={handleSubmit}>
          <div className="space-y-6">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Required Parameters</h3>
              <div>
                <Label htmlFor="max_number">Maximum Number</Label>
                <Input
                  id="max_number"
                  name="max_number"
                  type="number"
                  value={config.max_number}
                  onChange={handleInputChange}
                  required
                  className="bg-background border-0 px-2 h-auto focus-visible:ring-0 
                    focus-visible:ring-offset-0 placeholder:text-muted-foreground rounded-md"
                />
                <p className="text-sm text-gray-500 mt-1">Maximum number of items in dataset. Actual number may be lower if fewer records are returned.</p>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="balance_dataset"
                  checked={config.balance_dataset}
                  onCheckedChange={handleSwitchChange("balance_dataset")}
                />
                <Label htmlFor="balance_dataset">Balance Dataset</Label>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <HelpCircle className="h-4 w-4 text-gray-500" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Balancing the dataset ensures an equal distribution of classes, which can improve model performance.</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <p className="text-sm text-gray-500 mt-1">Ensures an equal distribution of classes to improve model performance.</p>
            </div>
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Optional Parameters</h3>
              <div>
                <Label htmlFor="min_feedback" className="flex items-center space-x-2">
                  <span>Minimum Feedback</span>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="h-4 w-4 text-gray-500" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Minimum number of feedback entries required for an item to be included in the dataset.</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </Label>
                <Input
                  id="min_feedback"
                  name="min_feedback"
                  type="number"
                  min="0"
                  value={config.min_feedback}
                  onChange={handleInputChange}
                  className="bg-background border-0 px-2 h-auto focus-visible:ring-0 
                    focus-visible:ring-offset-0 placeholder:text-muted-foreground rounded-md"
                />
                <p className="text-sm text-gray-500 mt-1">Number of feedback entries required for an item to be included.</p>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="feedback_agreement"
                  checked={config.feedback_agreement}
                  onCheckedChange={handleSwitchChange("feedback_agreement")}
                />
                <Label htmlFor="feedback_agreement" className="flex items-center space-x-2">
                  <span>Feedback Agreement</span>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="h-4 w-4 text-gray-500" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Only include items where all feedback entries agree with the assigned value.</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </Label>
              </div>
              <p className="text-sm text-gray-500 mt-1">Only include items where all feedback entries agree with the assigned value.</p>
              <div>
                <Label htmlFor="score_value" className="flex items-center space-x-2">
                  <span>Score Value</span>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <HelpCircle className="h-4 w-4 text-gray-500" />
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Only include items where the score value matches this value.</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </Label>
                <Input
                  id="score_value"
                  name="score_value"
                  type="number"
                  min="0"
                  value={config.score_value}
                  onChange={handleInputChange}
                  className="bg-background border-0 px-2 h-auto focus-visible:ring-0 
                    focus-visible:ring-offset-0 placeholder:text-muted-foreground rounded-md"
                />
                <p className="text-sm text-gray-500 mt-1">Only include items where the score value matches this value.</p>
              </div>
            </div>
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">SQL Query Template</h3>
              <p className="text-sm text-gray-500">Edit the SQL query template below. This template will be used to build the final SQL query using the above values.</p>
              <Collapsible open={isQueryVisible} onOpenChange={setIsQueryVisible}>
                <div className="flex items-center space-x-2">
                  <CollapsibleTrigger asChild>
                    <Button variant="ghost" size="sm" className="p-0">
                      {isQueryVisible ? <ChevronUpIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
                      <span className="ml-2">Edit SQL Query Template</span>
                    </Button>
                  </CollapsibleTrigger>
                </div>
                <CollapsibleContent className="mt-2">
                  <Textarea
                    name="query"
                    value={config.query}
                    onChange={handleInputChange}
                    className="w-full h-96 p-2 text-sm font-mono border rounded-md"
                    placeholder="Enter your SQL query template here..."
                  />
                </CollapsibleContent>
              </Collapsible>
            </div>
          </div>
        </form>
      </div>

      <div className="flex-shrink-0 p-6 bg-card rounded-b-lg">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSubmit}>Save Configuration</Button>
        </div>
      </div>
    </div>
  )
}
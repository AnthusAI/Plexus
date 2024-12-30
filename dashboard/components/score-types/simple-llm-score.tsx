import React from 'react'
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"

interface SimpleLLMScoreProps {
  score: any
  onChange: (score: any) => void
}

const modelOptions = {
  "OpenAI": ["GPT-3.5-turbo", "GPT-4", "GPT-4-32k"],
  "Azure OpenAI": ["GPT-3.5-turbo", "GPT-4"],
  "AWS Bedrock": ["Claude", "Jurassic-2"],
  "Google Vertex": ["PaLM", "BERT"],
  "Anthropic": ["Claude", "Claude 2"]
}

export default function SimpleLLMScoreComponent({ score, onChange }: SimpleLLMScoreProps) {
  const handleProviderChange = (provider: string) => {
    onChange({ ...score, provider, modelName: '' })
  }

  const handleModelNameChange = (modelName: string) => {
    onChange({ ...score, modelName })
  }

  const handleFineTunedModelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...score, fineTunedModel: e.target.value })
  }

  const handleSystemPromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange({ ...score, systemPrompt: e.target.value })
  }

  const handleUserPromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange({ ...score, userPrompt: e.target.value })
  }

  const handleParseFromStartChange = (checked: boolean) => {
    onChange({ ...score, parseCompletionFromStart: checked })
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div>
          <Label htmlFor="provider">Model Provider</Label>
          <Select value={score.provider} onValueChange={handleProviderChange}>
            <SelectTrigger id="provider">
              <SelectValue placeholder="Select a provider" />
            </SelectTrigger>
            <SelectContent>
              {Object.keys(modelOptions).map((provider) => (
                <SelectItem key={provider} value={provider}>{provider}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="modelName">Model Name</Label>
          <Select value={score.modelName} onValueChange={handleModelNameChange}>
            <SelectTrigger id="modelName">
              <SelectValue placeholder="Select a model" />
            </SelectTrigger>
            <SelectContent>
              {score.provider && modelOptions[score.provider as keyof typeof modelOptions].map((model) => (
                <SelectItem key={model} value={model}>{model}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="fineTunedModel">Fine-Tuned Model</Label>
          <Input
            id="fineTunedModel"
            value={score.fineTunedModel || ''}
            onChange={handleFineTunedModelChange}
            placeholder="Enter fine-tuned model name..."
          />
        </div>
      </div>
      <div className="space-y-4">
        <div>
          <Label htmlFor="systemPrompt">System Prompt</Label>
          <Textarea
            id="systemPrompt"
            value={score.systemPrompt || ''}
            onChange={handleSystemPromptChange}
            placeholder="Enter system prompt..."
            rows={5}
          />
        </div>
        <div>
          <Label htmlFor="userPrompt">User Prompt</Label>
          <Textarea
            id="userPrompt"
            value={score.userPrompt || ''}
            onChange={handleUserPromptChange}
            placeholder="Enter user prompt..."
            rows={5}
          />
        </div>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="parseCompletionFromStart"
            checked={score.parseCompletionFromStart || false}
            onCheckedChange={handleParseFromStartChange}
          />
          <Label htmlFor="parseCompletionFromStart">
            Parse completion from the start
          </Label>
        </div>
      </div>
    </div>
  )
}

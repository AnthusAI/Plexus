import React, { useState } from 'react'
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardContent } from "@/components/ui/card"
import { Plus, X, Trash } from 'lucide-react'
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"

interface LangGraphScoreProps {
  score: any
  onChange: (score: any) => void
}

interface Node {
  id: string
  name: string
  inputs: { key: string; value: string }[]
  systemPrompt: string
  userPrompt: string
  parseCompletionFromStart: boolean
  outputs: { key: string; value: string }[]
}

const modelOptions = {
  "OpenAI": ["GPT-3.5-turbo", "GPT-4", "GPT-4-32k"],
  "Azure OpenAI": ["GPT-3.5-turbo", "GPT-4"],
  "AWS Bedrock": ["Claude", "Jurassic-2"],
  "Google Vertex": ["PaLM", "BERT"],
  "Anthropic": ["Claude", "Claude 2"]
}

export default function LangGraphScoreComponent({ score, onChange }: LangGraphScoreProps) {
  const [nodes, setNodes] = useState<Node[]>(score.nodes || [])

  const handleProviderChange = (provider: string) => {
    onChange({ ...score, provider, modelName: '' })
  }

  const handleModelNameChange = (modelName: string) => {
    onChange({ ...score, modelName })
  }

  const handleFineTunedModelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange({ ...score, fineTunedModel: e.target.value })
  }

  const addNode = () => {
    const newNode: Node = {
      id: Date.now().toString(),
      name: `Node ${nodes.length + 1}`,
      inputs: [],
      systemPrompt: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam euismod, nisl eget aliquam ultricies, nunc nisl aliquet nunc, vitae aliquam nisl nunc vitae nisl.",
      userPrompt: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam euismod, nisl eget aliquam ultricies, nunc nisl aliquet nunc, vitae aliquam nisl nunc vitae nisl.",
      parseCompletionFromStart: false,
      outputs: []
    }
    setNodes([...nodes, newNode])
    onChange({ ...score, nodes: [...nodes, newNode] })
  }

  const removeNode = (id: string) => {
    const updatedNodes = nodes.filter(node => node.id !== id)
    setNodes(updatedNodes)
    onChange({ ...score, nodes: updatedNodes })
  }

  const updateNode = (id: string, updatedNode: Partial<Node>) => {
    const updatedNodes = nodes.map(node => node.id === id ? { ...node, ...updatedNode } : node)
    setNodes(updatedNodes)
    onChange({ ...score, nodes: updatedNodes })
  }

  const addKeyValuePair = (nodeId: string, type: 'inputs' | 'outputs') => {
    const updatedNodes = nodes.map(node => {
      if (node.id === nodeId) {
        return {
          ...node,
          [type]: [...node[type], { key: '', value: '' }]
        }
      }
      return node
    })
    setNodes(updatedNodes)
    onChange({ ...score, nodes: updatedNodes })
  }

  const removeKeyValuePair = (nodeId: string, type: 'inputs' | 'outputs', index: number) => {
    const updatedNodes = nodes.map(node => {
      if (node.id === nodeId) {
        const updatedArray = [...node[type]]
        updatedArray.splice(index, 1)
        return {
          ...node,
          [type]: updatedArray
        }
      }
      return node
    })
    setNodes(updatedNodes)
    onChange({ ...score, nodes: updatedNodes })
  }

  const updateKeyValuePair = (nodeId: string, type: 'inputs' | 'outputs', index: number, key: string, value: string) => {
    const updatedNodes = nodes.map(node => {
      if (node.id === nodeId) {
        const updatedArray = [...node[type]]
        updatedArray[index] = { key, value }
        return {
          ...node,
          [type]: updatedArray
        }
      }
      return node
    })
    setNodes(updatedNodes)
    onChange({ ...score, nodes: updatedNodes })
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
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold">Nodes</h3>
          <Button onClick={addNode} variant="outline" size="sm">
            <Plus className="h-4 w-4 mr-2" /> Add Node
          </Button>
        </div>
        <div className="space-y-4">
          {nodes.map((node) => (
            <Card key={node.id}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <Input
                  value={node.name}
                  onChange={(e) => updateNode(node.id, { name: e.target.value })}
                  className="font-semibold"
                />
                <Button onClick={() => removeNode(node.id)} variant="ghost" size="sm">
                  <Trash className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label className="text-sm font-medium">Inputs</Label>
                    <Button onClick={() => addKeyValuePair(node.id, 'inputs')} variant="ghost" size="sm" className="h-8 w-8 p-0">
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                  {node.inputs.map((input, index) => (
                    <div key={index} className="flex space-x-2">
                      <Input
                        value={input.key}
                        onChange={(e) => updateKeyValuePair(node.id, 'inputs', index, e.target.value, input.value)}
                        placeholder="Key"
                      />
                      <Input
                        value={input.value}
                        onChange={(e) => updateKeyValuePair(node.id, 'inputs', index, input.key, e.target.value)}
                        placeholder="Value"
                      />
                      <Button onClick={() => removeKeyValuePair(node.id, 'inputs', index)} variant="ghost" size="sm" className="h-8 w-8 p-0">
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`systemPrompt-${node.id}`}>System Prompt</Label>
                  <Textarea
                    id={`systemPrompt-${node.id}`}
                    value={node.systemPrompt}
                    onChange={(e) => updateNode(node.id, { systemPrompt: e.target.value })}
                    rows={5}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`userPrompt-${node.id}`}>User Prompt</Label>
                  <Textarea
                    id={`userPrompt-${node.id}`}
                    value={node.userPrompt}
                    onChange={(e) => updateNode(node.id, { userPrompt: e.target.value })}
                    rows={5}
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id={`parseCompletionFromStart-${node.id}`}
                    checked={node.parseCompletionFromStart}
                    onCheckedChange={(checked) => updateNode(node.id, { parseCompletionFromStart: checked === true })}
                  />
                  <Label htmlFor={`parseCompletionFromStart-${node.id}`}>Parse completion from the start</Label>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label className="text-sm font-medium">Outputs</Label>
                    <Button onClick={() => addKeyValuePair(node.id, 'outputs')} variant="ghost" size="sm" className="h-8 w-8 p-0">
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                  {node.outputs.map((output, index) => (
                    <div key={index} className="flex space-x-2">
                      <Input
                        value={output.key}
                        onChange={(e) => updateKeyValuePair(node.id, 'outputs', index, e.target.value, output.value)}
                        placeholder="Key"
                      />
                      <Input
                        value={output.value}
                        onChange={(e) => updateKeyValuePair(node.id, 'outputs', index, output.key, e.target.value)}
                        placeholder="Value"
                      />
                      <Button onClick={() => removeKeyValuePair(node.id, 'outputs', index)} variant="ghost" size="sm" className="h-8 w-8 p-0">
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}

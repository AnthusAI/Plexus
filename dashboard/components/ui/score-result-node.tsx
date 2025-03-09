import React, { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface ScoreResultNodeProps {
  name: string
  inputs: Record<string, any>
  outputs: Record<string, any>
}

export function ScoreResultNode({ name, inputs, outputs }: ScoreResultNodeProps) {
  const [isInputsExpanded, setIsInputsExpanded] = useState(false)
  const [isOutputsExpanded, setIsOutputsExpanded] = useState(true)

  // Format a value for display based on its type
  const formatValue = (value: any) => {
    if (value === null || value === undefined) {
      return <span className="text-muted-foreground italic">null</span>;
    }
    
    if (typeof value === 'string') {
      // For long text content, use pre-wrap to preserve formatting
      if (value.length > 100 || value.includes('\n')) {
        return (
          <pre className="text-xs whitespace-pre-wrap overflow-x-auto bg-background/50 p-2 rounded max-h-[300px] overflow-y-auto">
            {value}
          </pre>
        );
      }
      return <span className="text-foreground">{value}</span>;
    }
    
    if (typeof value === 'number' || typeof value === 'boolean') {
      return <span className="text-foreground">{String(value)}</span>;
    }
    
    // For objects and arrays, format as JSON
    try {
      return (
        <pre className="text-xs whitespace-pre-wrap overflow-x-auto bg-background/50 p-2 rounded max-h-[300px] overflow-y-auto">
          {JSON.stringify(value, null, 2)}
        </pre>
      );
    } catch (e) {
      return <span className="text-foreground">{String(value)}</span>;
    }
  }

  // Render a section with field headers and values
  const renderFields = (data: Record<string, any>) => {
    return Object.entries(data).map(([key, value]) => (
      <div key={key} className="mb-3 last:mb-0">
        <div className="text-xs font-medium text-muted-foreground mb-1 font-mono">{key}</div>
        <div className="pl-2 border-l-2 border-border">
          {formatValue(value)}
        </div>
      </div>
    ));
  }

  return (
    <div className="bg-card rounded-lg p-4 mb-3 last:mb-0">
      <div className="font-mono text-sm font-medium mb-2">{name}</div>
      
      {/* Inputs Section */}
      <div className="mb-3">
        <div 
          className="flex items-center justify-between cursor-pointer" 
          onClick={() => setIsInputsExpanded(!isInputsExpanded)}
        >
          <span className="text-xs text-muted-foreground font-semibold">Inputs</span>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
            {isInputsExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
        
        {isInputsExpanded && (
          <div className="mt-2">
            {Object.keys(inputs).length > 0 ? (
              renderFields(inputs)
            ) : (
              <div className="text-xs text-muted-foreground italic">No inputs</div>
            )}
          </div>
        )}
      </div>
      
      {/* Outputs Section */}
      <div>
        <div 
          className="flex items-center justify-between cursor-pointer" 
          onClick={() => setIsOutputsExpanded(!isOutputsExpanded)}
        >
          <span className="text-xs text-muted-foreground font-semibold">Outputs</span>
          <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
            {isOutputsExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
        
        {isOutputsExpanded && (
          <div className="mt-2">
            {Object.keys(outputs).length > 0 ? (
              renderFields(outputs)
            ) : (
              <div className="text-xs text-muted-foreground italic">No outputs</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
} 
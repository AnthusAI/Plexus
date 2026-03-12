import React, { useState } from 'react'
import { ChevronDown, ChevronUp, Scale } from 'lucide-react'
import { Button } from '@/components/ui/button'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'

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
      // For long text content, try to render as markdown first, fallback to pre-wrap
      if (value.length > 100 || value.includes('\n')) {
        // Check if it looks like markdown (has markdown syntax)
        const hasMarkdownSyntax = /[*_#`\[\](){}]|^\s*[-+*]\s+|^\s*\d+\.\s+/m.test(value);
        
        if (hasMarkdownSyntax) {
          return (
            <div className="text-xs bg-background/50 p-2 rounded max-h-[300px] overflow-y-auto prose prose-xs max-w-none prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkBreaks]}
                components={{
                  p: ({ children }) => <p className="mb-1 last:mb-0 text-xs">{children}</p>,
                  ul: ({ children }) => <ul className="mb-1 ml-3 list-disc">{children}</ul>,
                  ol: ({ children }) => <ol className="mb-1 ml-3 list-decimal">{children}</ol>,
                  li: ({ children }) => <li className="mb-0.5">{children}</li>,
                  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                  em: ({ children }) => <em className="italic">{children}</em>,
                  code: ({ children }) => <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                  pre: ({ children }) => <pre className="bg-muted p-1 rounded overflow-x-auto text-xs">{children}</pre>,
                  h1: ({ children }) => <h1 className="text-xs font-semibold mb-1 text-foreground">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-xs font-semibold mb-1 text-foreground">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-xs font-medium mb-1 text-foreground">{children}</h3>,
                }}
              >
                {value}
              </ReactMarkdown>
            </div>
          );
        } else {
          return (
            <pre className="text-xs whitespace-pre-wrap overflow-x-auto bg-background/50 p-2 rounded max-h-[300px] overflow-y-auto">
              {value}
            </pre>
          );
        }
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
    <div className="bg-background rounded-lg p-4 mb-3 last:mb-0">
      <div className="flex items-center justify-between mb-2">
        <div className="font-mono text-sm font-medium">{name}</div>
        <div className="flex items-start gap-2">
          <div className="text-sm text-muted-foreground text-right">
            Decision<br />
            Node
          </div>
          <Scale className="h-[2.25rem] w-[2.25rem] text-muted-foreground" strokeWidth={1.25} />
        </div>
      </div>
      
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
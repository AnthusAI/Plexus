import React from 'react'
import { View } from 'lucide-react'
import { ScoreResultNode } from './score-result-node'

export interface TraceNode {
  name: string
  inputs: Record<string, any>
  outputs: Record<string, any>
}

export interface ScoreResultTraceProps {
  trace: any | null
  variant?: 'default' | 'compact'
  className?: string
}

export function ScoreResultTrace({ 
  trace, 
  variant = 'default',
  className = '' 
}: ScoreResultTraceProps) {
  // Parse trace data and normalize to node format
  const parsedTraceNodes = React.useMemo<TraceNode[] | null>(() => {
    if (!trace) return null;
    
    try {
      // Parse string trace if needed
      let traceData = trace;
      if (typeof trace === 'string') {
        try {
          traceData = JSON.parse(trace);
        } catch (e) {
          console.error('Error parsing trace data:', e);
          return null;
        }
      }
      
      // Handle different trace formats
      
      // Format 1: node_results format (from example)
      if (traceData && typeof traceData === 'object' && Array.isArray(traceData.node_results)) {
        return traceData.node_results.map((node: any) => ({
          name: node.node_name || 'Unnamed Node',
          inputs: node.input || {},
          outputs: node.output || {}
        }));
      }
      
      // Format 2: Array of nodes with inputs/outputs already defined
      if (Array.isArray(traceData)) {
        return traceData.map((node: any) => ({
          name: node.name || 'Unnamed Node',
          inputs: node.inputs || {},
          outputs: node.outputs || {}
        }));
      }
      
      // Format 3: Object with 'steps' array
      if (traceData && typeof traceData === 'object' && Array.isArray(traceData.steps)) {
        return traceData.steps.map((step: any) => ({
          name: step.name || 'Unnamed Step',
          inputs: step.input || step.inputs || {},
          outputs: step.output || step.outputs || {}
        }));
      }
      
      // Format 4: Object with nodes/steps under a different key
      const possibleStepKeys = ['nodes', 'steps', 'traces', 'operations', 'executions'];
      for (const key of possibleStepKeys) {
        if (traceData && typeof traceData === 'object' && Array.isArray(traceData[key])) {
          return traceData[key].map((item: any) => ({
            name: item.name || `Unnamed ${key.slice(0, -1)}`,
            inputs: item.input || item.inputs || {},
            outputs: item.output || item.outputs || {}
          }));
        }
      }
      
      // If we can't determine the format, return null for fallback display
      return null;
    } catch (e) {
      console.error('Error processing trace data:', e);
      return null;
    }
  }, [trace]);

  // Get the raw trace data for fallback display
  const rawTraceData = React.useMemo(() => {
    if (!trace) return null;
    
    try {
      if (typeof trace === 'string') {
        try {
          return JSON.parse(trace);
        } catch (e) {
          return trace;
        }
      }
      return trace;
    } catch (e) {
      return String(trace);
    }
  }, [trace]);

  // Don't render anything if there's no trace data
  if (!trace) return null;

  const containerClasses = variant === 'compact' 
    ? 'space-y-2' 
    : 'space-y-3';
  
  return (
    <div className={className}>
      {/* Parsed trace nodes */}
      {parsedTraceNodes && parsedTraceNodes.length > 0 && (
        <div className="bg-background rounded-lg p-3">
          <div className={containerClasses}>
            {parsedTraceNodes.map((node, index) => (
              <ScoreResultNode
                key={`${node.name || 'node'}-${index}`}
                name={node.name}
                inputs={node.inputs}
                outputs={node.outputs}
              />
            ))}
          </div>
        </div>
      )}

      {/* Fallback for raw trace data */}
      {!parsedTraceNodes && rawTraceData && (
        <div className="bg-background rounded-lg p-3">
          <pre className="text-xs whitespace-pre-wrap overflow-x-auto max-h-[400px] overflow-y-auto">
            {typeof rawTraceData === 'string' 
              ? rawTraceData 
              : JSON.stringify(rawTraceData, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
} 
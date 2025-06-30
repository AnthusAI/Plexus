import React from 'react';
import { ReportBlockProps, BlockComponent } from './ReportBlock';
import { Badge } from '@/components/ui/badge';

/**
 * Specialized block for displaying Score Information.
 * Renders the internal content, assuming the BlockRenderer provides the outer container.
 */
const ScoreInfo: React.FC<ReportBlockProps> = ({ 
  config,
  output,
  log,
  name,
  position,
  children
}) => {
  // Handle both string and object output formats
  let data: Record<string, any> = {};
  try {
    if (typeof output === 'string') {
      // Parse string output as JSON
      data = JSON.parse(output);
    } else {
      // Use object output directly
      data = output || {};
    }
  } catch (error) {
    console.error('Failed to parse ScoreInfo output:', error);
    data = {};
  }
  
  // Format a percentage display with 1 decimal place
  const formatPercent = (value: number | undefined) => {
    if (value === undefined) return 'N/A';
    return `${(value * 100).toFixed(1)}%`;
  };
  
  // Format a date for display
  const formatDate = (dateStr: string | undefined) => {
    if (!dateStr) return 'N/A';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return dateStr;
    }
  };
  
  // Return only the inner content structure
  return (
    <>
      <div className="pb-2">
        <h3 className="text-lg font-medium">{name || data.name || 'Score Information'}</h3>
      </div>
      <div className="space-y-4">
        {data.name && (
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium">Name:</span>
            <span className="text-sm">{data.name}</span>
          </div>
        )}
        
        {data.description && (
          <div className="flex justify-between items-start">
            <span className="text-sm font-medium">Description:</span>
            <span className="text-sm text-right max-w-[70%]">{data.description}</span>
          </div>
        )}
        
        {data.accuracy !== undefined && (
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium">Accuracy:</span>
            <Badge variant={data.accuracy > 0.8 ? "success" : data.accuracy > 0.6 ? "secondary" : "destructive"}>
              {formatPercent(data.accuracy)}
            </Badge>
          </div>
        )}
        
        {data.value !== undefined && (
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium">Value:</span>
            <Badge variant={data.value > 0.8 ? "success" : data.value > 0.6 ? "secondary" : "destructive"}>
              {formatPercent(data.value)}
            </Badge>
          </div>
        )}
        
        {data.updatedAt && (
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium">Last Updated:</span>
            <span className="text-sm">{formatDate(data.updatedAt)}</span>
          </div>
        )}
      </div>
    </>
  );
};

// Set the blockClass for registration
(ScoreInfo as BlockComponent).blockClass = 'ScoreInfo';

export default ScoreInfo; 
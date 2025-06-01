"use client";

import React, { useState, useMemo } from 'react';
import { IdCard, ChevronDown, ChevronRight, Copy } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

export interface IdentifierItem {
  name: string;      // Required: "Customer ID", "Order ID", etc.
  value: string;     // Required: "CUST-123456", "ORD-789012", etc. (renamed from 'id')
  url?: string;      // Optional: clickable link
}

// Legacy interface for backward compatibility
interface LegacyIdentifier {
  name: string;
  id: string;    // Legacy: will be mapped to 'value'
  url?: string;
}

interface IdentifierDisplayProps {
  externalId?: string;
  identifiers?: string | IdentifierItem[]; // Can be JSON string or array
  className?: string;
  iconSize?: 'sm' | 'md' | 'lg';
  textSize?: 'xs' | 'sm' | 'base';
  skeletonMode?: boolean;
  displayMode?: 'full' | 'compact'; // New prop to control functionality
}

export const IdentifierDisplay: React.FC<IdentifierDisplayProps> = ({
  externalId,
  identifiers,
  className,
  iconSize = 'sm',
  textSize = 'xs',
  skeletonMode = false,
  displayMode = 'full'
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const copyToClipboard = async (value: string, label?: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`Copied ${label || 'identifier'} to clipboard`);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
      toast.error('Failed to copy to clipboard');
    }
  };

  const parsedIdentifiers = useMemo(() => {
    if (!identifiers) return [];
    
    // If it's already an array, use it directly
    if (Array.isArray(identifiers)) {
      return identifiers;
    }
    
    // If it's a string, parse it as JSON
    if (typeof identifiers === 'string') {
      try {
        const parsed = JSON.parse(identifiers) as LegacyIdentifier[];
        // Map legacy 'id' field to 'value' field for consistency
        return parsed.map(item => ({
          name: item.name,
          value: item.id, // Map legacy 'id' to 'value'
          url: item.url
        }));
      } catch (error) {
        console.error('Failed to parse identifiers JSON string:', error);
        return [];
      }
    }
    
    return [];
  }, [identifiers]);

  // Determine what to show
  const hasComplexIdentifiers = parsedIdentifiers.length > 0;
  const firstIdentifier = hasComplexIdentifiers ? parsedIdentifiers[0] : null;
  
  // If no complex identifiers, fall back to externalId
  if (!hasComplexIdentifiers && !externalId) {
    return null;
  }

  const iconClasses = cn(
    iconSize === 'sm' && 'h-3 w-3 flex-shrink-0',
    iconSize === 'md' && 'h-4 w-4 flex-shrink-0', 
    iconSize === 'lg' && 'h-5 w-5 flex-shrink-0'
  );

  const baseTextSize = textSize === 'xs' ? 'text-xs' : textSize === 'sm' ? 'text-sm' : 'text-base';
  const textClasses = cn(baseTextSize, 'flex-shrink-0');
  const labelTextClasses = cn('!text-xs', 'font-medium flex-shrink-0 text-muted-foreground w-12');

  // Skeleton mode rendering
  if (skeletonMode) {
    const finalTextClasses = cn(textClasses, className);
    return (
      <div className={cn("flex items-start gap-1 text-muted-foreground min-w-0", finalTextClasses)}>
        <div className={cn(iconClasses, "bg-muted rounded animate-pulse")} />
        <div className="h-3 w-20 bg-muted rounded animate-pulse" />
      </div>
    );
  }

  const renderIdentifierValue = (identifier: IdentifierItem) => {
    const displayValue = identifier.value.length > 25 
      ? `${identifier.value.substring(0, 25)}...` 
      : identifier.value;

    const valueElement = identifier.url ? (
      <a 
        href={identifier.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline !text-xs"
        title={identifier.value}
      >
        {displayValue}
      </a>
    ) : (
      <span title={identifier.value} className="!text-xs text-muted-foreground">
        {displayValue}
      </span>
    );

    // Only show copy button in full mode
    if (displayMode === 'compact') {
      return valueElement;
    }

    return (
      <div className="flex items-center gap-1">
        {valueElement}
        <button
          onClick={() => copyToClipboard(identifier.value, identifier.name)}
          className="p-0.5 hover:bg-muted rounded flex-shrink-0 opacity-60 hover:opacity-100"
          title={`Copy ${identifier.name}`}
        >
          <Copy className="h-3 w-3" />
        </button>
      </div>
    );
  };

  const renderSimpleExternalId = () => {
    const finalTextClasses = cn(textClasses, className);
    
    // Compact mode - no copy button
    if (displayMode === 'compact') {
      return (
        <div className={cn("flex items-start gap-1 text-muted-foreground", finalTextClasses)}>
          <IdCard className={iconClasses} />
          <span className="!text-xs text-muted-foreground">{externalId}</span>
        </div>
      );
    }

    // Full mode - with copy button
    return (
      <div className={cn("flex items-start gap-1 text-muted-foreground", finalTextClasses)}>
        <IdCard className={iconClasses} />
        <span className="!text-xs text-muted-foreground">{externalId}</span>
        <button
          onClick={() => copyToClipboard(externalId!, "External ID")}
          className="p-0.5 hover:bg-muted rounded flex-shrink-0 opacity-60 hover:opacity-100"
          title="Copy External ID"
        >
          <Copy className="h-3 w-3" />
        </button>
      </div>
    );
  };

  if (!hasComplexIdentifiers) {
    return renderSimpleExternalId();
  }

  const hasMultipleIdentifiers = parsedIdentifiers.length > 1;

  const finalTextClasses = cn(textClasses, className);

  // Calculate the left margin to align with the text (icon width + gap)
  const expandedLeftMargin = cn(
    iconSize === 'sm' && 'ml-4', // 12px icon + 4px gap = 16px = ml-4
    iconSize === 'md' && 'ml-5', // 16px icon + 4px gap = 20px = ml-5
    iconSize === 'lg' && 'ml-6'  // 20px icon + 4px gap = 24px = ml-6
  );

  return (
    <div>
      {/* First identifier with icon and optional expander */}
      <div className={cn("flex items-start gap-1 text-muted-foreground", finalTextClasses)}>
        <IdCard className={iconClasses} />
        <span className={labelTextClasses}>
          {firstIdentifier!.name}:
        </span>
        <div className="flex-1 min-w-0">
          {renderIdentifierValue(firstIdentifier!)}
        </div>
        {/* Only show expand/collapse button in full mode and when there are multiple identifiers */}
        {displayMode === 'full' && hasMultipleIdentifiers && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="ml-1 p-0.5 hover:bg-muted rounded flex-shrink-0"
            aria-label={isExpanded ? "Collapse identifiers" : "Expand identifiers"}
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        )}
      </div>

      {/* Additional identifiers when expanded - only in full mode */}
      {displayMode === 'full' && isExpanded && hasMultipleIdentifiers && (
        <div className={expandedLeftMargin}>
          {parsedIdentifiers.slice(1).map((identifier, index) => (
            <div key={`${identifier.name}-${index + 1}`} className="flex items-start gap-1">
              <span className={labelTextClasses}>
                {identifier.name}:
              </span>
              <div className="flex-1 min-w-0">
                {renderIdentifierValue(identifier)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default IdentifierDisplay;
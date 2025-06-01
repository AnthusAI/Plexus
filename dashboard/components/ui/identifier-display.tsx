"use client";

import React, { useState, useMemo } from 'react';
import { IdCard, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

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
}

export const IdentifierDisplay: React.FC<IdentifierDisplayProps> = ({
  externalId,
  identifiers,
  className,
  iconSize = 'sm',
  textSize = 'xs',
  skeletonMode = false
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

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
  const labelTextClasses = cn('!text-xs', 'font-medium flex-shrink-0 text-muted-foreground');
  const valueTextClasses = cn('!text-xs', 'truncate min-w-0 flex-1 text-muted-foreground');

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
    const displayValue = identifier.value.length > 15 
      ? `${identifier.value.substring(0, 15)}...` 
      : identifier.value;

    if (identifier.url) {
      return (
        <a 
          href={identifier.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline !text-xs"
          title={identifier.value}
        >
          {displayValue}
        </a>
      );
    }

    return (
      <span title={identifier.value} className="!text-xs text-muted-foreground">
        {displayValue}
      </span>
    );
  };

  const renderSimpleExternalId = () => {
    const finalTextClasses = cn(textClasses, className);
    return (
      <div className={cn("flex items-start gap-1 text-muted-foreground min-w-0", finalTextClasses)}>
        <IdCard className={iconClasses} />
        <span className="truncate !text-xs text-muted-foreground">{externalId}</span>
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
      <div className={cn("flex items-start gap-1 text-muted-foreground min-w-0", finalTextClasses)}>
        <IdCard className={iconClasses} />
        <span className={labelTextClasses}>
          {firstIdentifier!.name}:
        </span>
        <span className={valueTextClasses}>
          {renderIdentifierValue(firstIdentifier!)}
        </span>
        {hasMultipleIdentifiers && (
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

      {/* Additional identifiers when expanded */}
      {isExpanded && hasMultipleIdentifiers && (
        <div className={expandedLeftMargin}>
          {parsedIdentifiers.slice(1).map((identifier, index) => (
            <div key={`${identifier.name}-${index + 1}`} className="flex items-start gap-1">
              <span className={labelTextClasses}>
                {identifier.name}:
              </span>
              <span className="!text-xs text-muted-foreground">
                {renderIdentifierValue(identifier)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default IdentifierDisplay;
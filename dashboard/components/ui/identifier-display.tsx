"use client";

import React, { useState, useMemo } from 'react';
import { IdCard, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Identifier {
  name: string;
  id: string;
  url?: string;
}

interface IdentifierDisplayProps {
  externalId?: string;
  identifiers?: string; // JSON string
  className?: string;
  iconSize?: 'sm' | 'md' | 'lg';
  textSize?: 'xs' | 'sm' | 'base';
}

export const IdentifierDisplay: React.FC<IdentifierDisplayProps> = ({
  externalId,
  identifiers,
  className,
  iconSize = 'sm',
  textSize = 'xs'
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const parsedIdentifiers = useMemo(() => {
    if (identifiers) {
      try {
        return JSON.parse(identifiers) as Identifier[];
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

  const textClasses = cn(
    textSize === 'xs' && 'text-xs',
    textSize === 'sm' && 'text-sm',
    textSize === 'base' && 'text-base',
    'flex-shrink-0'
  );

  const renderIdentifierValue = (identifier: Identifier) => {
    const displayValue = identifier.id.length > 15 
      ? `${identifier.id.substring(0, 15)}...` 
      : identifier.id;

    if (identifier.url) {
      return (
        <a 
          href={identifier.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
          title={identifier.id}
        >
          {displayValue}
        </a>
      );
    }

    return (
      <span title={identifier.id}>
        {displayValue}
      </span>
    );
  };

  const renderSimpleExternalId = () => (
    <div className={cn("flex items-start gap-1 text-muted-foreground min-w-0", textClasses, className)}>
      <IdCard className={iconClasses} />
      <span className="truncate">{externalId}</span>
    </div>
  );

  if (!hasComplexIdentifiers) {
    return renderSimpleExternalId();
  }

  const hasMultipleIdentifiers = parsedIdentifiers.length > 1;

  return (
    <div className={className}>
      {/* First identifier with icon and optional expander */}
      <div className={cn("flex items-start gap-1 text-muted-foreground min-w-0", textClasses)}>
        <IdCard className={iconClasses} />
        <span className={cn(textClasses, "font-medium flex-shrink-0")}>
          {firstIdentifier!.name}:
        </span>
        <span className={cn(textClasses, "truncate min-w-0 flex-1")}>
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
        <div className="mt-1 ml-5 space-y-1">
          {parsedIdentifiers.slice(1).map((identifier, index) => (
            <div key={`${identifier.name}-${index + 1}`} className="flex items-start gap-1">
              <span className={cn(textClasses, "font-medium")}>
                {identifier.name}:
              </span>
              <span className={textClasses}>
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
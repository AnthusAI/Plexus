'use client';

import React, { useState } from 'react';
import { MessageSquareCode, Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';

export interface CodeSnippetProps {
  code: string;
  type?: 'YAML' | 'JSON';
  title?: string;
  description?: string;
  autoExpandCopy?: boolean; // Auto-copy when expanded
  className?: string;
}

/**
 * CodeSnippet Component
 * 
 * A reusable component for displaying Universal Code Snippets (YAML/JSON) with contextual information.
 * Features the Universal Code Icon to indicate code intended for humans, AI models, and other code.
 * Includes clipboard copy functionality with toast notifications.
 */
export const CodeSnippet: React.FC<CodeSnippetProps> = ({
  code,
  type = 'YAML',
  title,
  description,
  autoExpandCopy = true,
  className = ''
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const handleToggleExpand = async () => {
    const wasExpanded = isExpanded;
    setIsExpanded(!isExpanded);

    // Auto-copy when expanding (not when collapsing)
    if (!wasExpanded && autoExpandCopy) {
      await handleCopy();
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setIsCopied(true);
      toast({
        description: "Copied code to clipboard",
        duration: 2000,
      });
      
      // Reset copy state after 2 seconds
      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
      toast({
        variant: "destructive",
        description: "Failed to copy code to clipboard",
        duration: 2000,
      });
    }
  };

  const defaultTitle = `Code Output (${type})`;
  const defaultDescription = type === 'YAML' 
    ? "Structured YAML code with contextual information for humans, AI models, and other code"
    : "JSON code output from the system";

  return (
    <div className={`bg-card border rounded-lg overflow-hidden ${className}`}>
      {/* Header with expand/collapse button */}
      <div className="flex items-center justify-between p-3 border-b bg-card/50">
        <div className="flex items-center gap-2">
          <MessageSquareCode className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">{title || defaultTitle}</span>
        </div>
        <div className="flex items-center gap-2">
          {isExpanded && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className="h-7 px-2"
            >
              {isCopied ? (
                <>
                  <Check className="h-3 w-3 mr-1" />
                  <span className="text-xs">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3 mr-1" />
                  <span className="text-xs">Copy</span>
                </>
              )}
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={handleToggleExpand}
            className="h-7 px-3"
          >
            <MessageSquareCode className="h-3 w-3 mr-1" />
            <span className="text-xs">{isExpanded ? "Hide Code" : "Code"}</span>
          </Button>
        </div>
      </div>

      {/* Description */}
      {isExpanded && (
        <div className="px-3 py-2 bg-muted/30 border-b">
          <p className="text-xs text-muted-foreground">
            {description || defaultDescription}
          </p>
        </div>
      )}

      {/* Code content */}
      {isExpanded && (
        <div className="relative">
          <pre className="p-4 text-xs overflow-auto max-h-96 bg-card">
            <code className="text-foreground whitespace-pre-wrap break-words">
              {code}
            </code>
          </pre>
        </div>
      )}
    </div>
  );
};
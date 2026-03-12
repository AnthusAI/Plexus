/**
 * Utility functions for formatting text in narrow diagram columns
 */

/**
 * Splits a long string into multiple lines for narrow column display
 * @param text - The text to format
 * @param maxLineLength - Maximum characters per line (default: 8)
 * @returns Formatted text with line breaks
 */
export function formatForNarrowColumn(text: string, maxLineLength: number = 8): string {
  if (!text) return '';
  
  // If text is short enough, return as-is
  if (text.length <= maxLineLength) {
    return text;
  }
  
  // Split on common delimiters first
  const parts = text.split(/[-_\s:]/);
  
  if (parts.length > 1) {
    // Join parts with line breaks, respecting max length
    const lines: string[] = [];
    let currentLine = '';
    
    for (const part of parts) {
      if (part.length === 0) continue;
      
      if (currentLine.length === 0) {
        currentLine = part;
      } else if ((currentLine + part).length <= maxLineLength) {
        currentLine += part;
      } else {
        lines.push(currentLine);
        currentLine = part;
      }
    }
    
    if (currentLine.length > 0) {
      lines.push(currentLine);
    }
    
    return lines.join('\n');
  }
  
  // If no delimiters, split by character count
  const lines: string[] = [];
  for (let i = 0; i < text.length; i += maxLineLength) {
    lines.push(text.slice(i, i + maxLineLength));
  }
  
  return lines.join('\n');
}

/**
 * Formats a model name for narrow column display
 * Handles common patterns like "gpt-4o-mini", "claude-3-sonnet", etc.
 */
export function formatModelName(modelName: string): string {
  if (!modelName) return '';
  
  // Split on hyphens and format each part
  const parts = modelName.split('-');
  
  if (parts.length <= 2) {
    return parts.join('\n');
  }
  
  // For longer model names, group intelligently
  const formatted: string[] = [];
  let currentGroup = '';
  
  for (const part of parts) {
    if (currentGroup.length === 0) {
      currentGroup = part;
    } else if ((currentGroup + part).length <= 6) {
      currentGroup += part;
    } else {
      formatted.push(currentGroup);
      currentGroup = part;
    }
  }
  
  if (currentGroup.length > 0) {
    formatted.push(currentGroup);
  }
  
  return formatted.join('\n');
}

/**
 * Formats a number with appropriate units for narrow display
 */
export function formatNumberForColumn(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  } else if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  return num.toString();
}

/**
 * Formats preprocessing method with sample size
 */
export function formatPreprocessor(method: string, sampleSize?: number): string {
  let result = '';
  
  if (sampleSize) {
    const formattedSize = formatNumberForColumn(sampleSize);
    result = `item count:\n${formattedSize}`;
  }
  
  if (method) {
    if (result) {
      result += '\n\n';  // Add spacing between sections
    }
    
    // Map technical method names to user-friendly display names
    const displayMethod = method === 'itemize' ? 'one-to-many' : method;
    
    // Handle special cases that shouldn't be split by formatForNarrowColumn
    if (displayMethod === 'one-to-many') {
      result += 'one-to-many';  // Keep as single line
    } else {
      result += formatForNarrowColumn(displayMethod);
    }
  }
  
  return result || 'preprocessing';
}

/**
 * Formats LLM provider, model, and prompt template for narrow display
 */
export function formatLLM(provider: string, model?: string, promptTemplate?: string): string {
  let result = formatForNarrowColumn(provider);
  
  if (model) {
    result += `\n\n${formatModelName(model)}`;
  } else {
    result += '\n\nextraction';
  }
  
  if (promptTemplate) {
    // Truncate prompt to reasonable length for display (130 chars - 30% more than 100)
    const maxPromptLength = 130;
    let truncatedPrompt = promptTemplate.length > maxPromptLength 
      ? promptTemplate.slice(0, maxPromptLength) + '...'
      : promptTemplate;
    
    // Hard wrap at 15 characters per line for narrow column (increased from 12)
    const maxLineLength = 15;
    const promptLines: string[] = [];
    
    for (let i = 0; i < truncatedPrompt.length; i += maxLineLength) {
      promptLines.push(truncatedPrompt.slice(i, i + maxLineLength));
    }
    
    result += '\n\n' + promptLines.join('\n');
  }
  
  return result;
}

/**
 * Formats BERTopic configuration for narrow display
 */
export function formatBERTopic(config: {
  minTopicSize?: number;
  requestedTopics?: number;
  minNgram?: number;
  maxNgram?: number;
  topNWords?: number;
  discoveredTopics?: number;
}): string {
  const lines: string[] = [];
  
  // Show requested topics first (input parameter)
  if (config.requestedTopics) {
    lines.push(`topic #: ${config.requestedTopics}`);
  }
  
  // Show minimum topic size (important parameter)
  if (config.minTopicSize) {
    lines.push(`min: ${config.minTopicSize}`);
  }
  
  // Show top N words if available
  if (config.topNWords) {
    lines.push(`words: ${config.topNWords}`);
  }
  
  // Show n-gram range if available
  if (config.minNgram && config.maxNgram) {
    lines.push(`${config.minNgram}-${config.maxNgram}gram`);
  }
  
  // Show discovered topics count last (outcome/result)
  if (config.discoveredTopics !== undefined) {
    lines.push(`found: ${config.discoveredTopics}`);
  }
  
  return lines.join('\n\n');
}

/**
 * Formats fine-tuning configuration for narrow display
 */
export function formatFineTuning(config: {
  useRepresentationModel: boolean;
  provider?: string;
  model?: string;
}): string {
  if (!config.useRepresentationModel) {
    return 'No\nfine-tuning';
  }
  
  const lines: string[] = [];
  
  // Show provider
  if (config.provider) {
    lines.push(formatForNarrowColumn(config.provider));
  }
  
  // Show model
  if (config.model) {
    lines.push(formatModelName(config.model));
  }
  
  // If we have provider or model, return them; otherwise fallback
  if (lines.length > 0) {
    return lines.join('\n\n');
  }
  
  return 'LLM\n\nfine-tuning';
} 
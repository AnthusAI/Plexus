import React from 'react'
import ReportBlock, { BlockComponent, ReportBlockProps } from './ReportBlock'
import { registerBlock } from './BlockRegistry'
import { parseOutputString } from '@/lib/utils'

interface TextBlockConfig {
  text: string
}

interface TextBlockOutput {
  text: string
}

const TextBlock: BlockComponent = (props: ReportBlockProps) => {
  const config = props.config as TextBlockConfig
  
  // Handle both string and object output formats
  let output: TextBlockOutput = { text: '' };
  try {
    if (typeof props.output === 'string') {
      // Use the safe parser that handles both JSON and YAML
      const parsed = parseOutputString(props.output);
      output = parsed as TextBlockOutput;
    } else {
      // Use object output directly
      output = props.output as TextBlockOutput;
    }
  } catch (error) {
    console.error('Failed to parse TextBlock output:', error);
    output = { text: '' };
  }

  // Debug logging to help identify the issue
  console.log('TextBlock debug:', {
    outputType: typeof output,
    outputKeys: output ? Object.keys(output) : [],
    textType: typeof output?.text,
    textValue: output?.text,
    configType: typeof config,
    configKeys: config ? Object.keys(config) : [],
    configTextType: typeof config?.text,
    configTextValue: config?.text
  });

  // Safety check: ensure we're rendering a string, not an object
  const getTextToRender = (): string => {
    const outputText = output?.text;
    const configText = config?.text;
    
    // If output.text exists and is a string, use it
    if (typeof outputText === 'string') {
      return outputText;
    }
    
    // If output.text is an object, try to stringify it or extract a meaningful value
    if (outputText && typeof outputText === 'object') {
      console.warn('TextBlock: output.text is an object, attempting to stringify:', outputText);
      return JSON.stringify(outputText, null, 2);
    }
    
    // Fall back to config.text if it's a string
    if (typeof configText === 'string') {
      return configText;
    }
    
    // If config.text is an object, stringify it
    if (configText && typeof configText === 'object') {
      console.warn('TextBlock: config.text is an object, attempting to stringify:', configText);
      return JSON.stringify(configText, null, 2);
    }
    
    // Final fallback
    return '';
  };

  const textToRender = getTextToRender();

  return (
    <div className="w-full min-w-0 max-w-full overflow-hidden my-4">
      <div className="prose max-w-none">
        {textToRender}
      </div>
    </div>
  )
}

TextBlock.blockClass = 'text-block'

// Register the block
registerBlock('text', TextBlock)

export default TextBlock 
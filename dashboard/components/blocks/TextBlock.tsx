import React from 'react'
import ReportBlock, { BlockComponent, ReportBlockProps } from './ReportBlock'
import { registerBlock } from './BlockRegistry'

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
      // Parse string output as JSON
      output = JSON.parse(props.output);
    } else {
      // Use object output directly
      output = props.output as TextBlockOutput;
    }
  } catch (error) {
    console.error('Failed to parse TextBlock output:', error);
    output = { text: '' };
  }

  return (
    <div className="w-full min-w-0 max-w-full overflow-hidden my-4">
      <div className="prose max-w-none">
        {output.text || config.text}
      </div>
    </div>
  )
}

TextBlock.blockClass = 'text-block'

// Register the block
registerBlock('text', TextBlock)

export default TextBlock 
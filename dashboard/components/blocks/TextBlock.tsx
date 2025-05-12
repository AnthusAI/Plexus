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
  const output = props.output as TextBlockOutput

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
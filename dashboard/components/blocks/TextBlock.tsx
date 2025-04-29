import React from 'react'
import { BaseBlock, BlockComponent, BlockProps } from './BaseBlock'
import { registerBlock } from './BlockRegistry'

interface TextBlockConfig {
  text: string
}

interface TextBlockOutput {
  text: string
}

const TextBlock: BlockComponent = (props: BlockProps) => {
  const config = props.config as TextBlockConfig
  const output = props.output as TextBlockOutput

  return (
    <BaseBlock {...props}>
      <div className="prose max-w-none">
        {output.text || config.text}
      </div>
    </BaseBlock>
  )
}

TextBlock.blockClass = 'text-block'

// Register the block
registerBlock('text', TextBlock)

export default TextBlock 
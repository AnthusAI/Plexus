import React from 'react'
import { BaseBlock, BlockComponent, BlockProps } from './BaseBlock'
import { registerBlock } from './BlockRegistry'

const DefaultBlock: BlockComponent = ({ output, ...props }) => {
  return (
    <div className="border border-border rounded-lg p-4 my-4 max-w-full">
      <div className="overflow-x-auto">
        <pre className="bg-muted p-2 rounded font-mono text-sm whitespace-pre max-w-full">
          {JSON.stringify(output, null, 2)}
        </pre>
      </div>
    </div>
  )
}

// Set the block class name
DefaultBlock.blockClass = 'default'

// Register the block
registerBlock('default', DefaultBlock)

export default DefaultBlock 
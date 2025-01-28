import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { ContainerBase } from '../components/workflow/base/container-base'
import { AudioNode } from '../components/workflow/nodes/audio-node'
import { ImageNode } from '../components/workflow/nodes/image-node'
import { TextNode } from '../components/workflow/nodes/text-node'

const meta = {
  title: 'Workflow Pictograms/Parts/Media Nodes',
  component: ContainerBase,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof ContainerBase>

export default meta
type Story = StoryObj<typeof ContainerBase>

const Container = ({ children }: { children: React.ReactNode }) => (
  <div className="resize overflow-auto border border-border rounded-lg p-4" 
       style={{ width: '90vw', height: '90vh', minWidth: '420px' }}>
    {children}
  </div>
)

export const MediaNodes = {
  render: () => (
    <Container>
      <ContainerBase viewBox="0 0 4 2">
        <g transform="translate(1, 1)">
          <AudioNode status="not-started" />
        </g>
        <g transform="translate(2, 1)">
          <ImageNode status="not-started" />
        </g>
        <g transform="translate(3, 1)">
          <TextNode status="not-started" />
        </g>
      </ContainerBase>
    </Container>
  ),
} 
import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { SegmentedProgressBar } from '../components/ui/segmented-progress-bar'

const meta: Meta<typeof SegmentedProgressBar> = {
  title: 'Components/SegmentedProgressBar',
  component: SegmentedProgressBar,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    state: {
      description: 'Current state of the progress bar',
      options: ['open', 'closed', 'processing', 'complete', 'error'],
      control: { type: 'radio' }
    }
  }
}

export default meta
type Story = StoryObj<typeof SegmentedProgressBar>

export const AllStates: Story = {
  render: () => (
    <div className="space-y-8 w-[600px]">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Open - Initial state</div>
        <SegmentedProgressBar state="open" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Closed - Ready for processing</div>
        <SegmentedProgressBar state="closed" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Processing - Currently running</div>
        <SegmentedProgressBar state="processing" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Complete - Successfully finished</div>
        <SegmentedProgressBar state="complete" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Error - Failed during processing</div>
        <SegmentedProgressBar state="error" />
      </div>
    </div>
  ),
}

export const Open: Story = {
  args: {
    state: 'open',
  },
  parameters: {
    docs: {
      description: {
        story: 'Initial state when the job is first created. Only the first segment is active.'
      }
    }
  }
}

export const Closed: Story = {
  args: {
    state: 'closed',
  },
  parameters: {
    docs: {
      description: {
        story: 'Job is closed and ready for processing. First two segments are active.'
      }
    }
  }
}

export const Processing: Story = {
  args: {
    state: 'processing',
  },
  parameters: {
    docs: {
      description: {
        story: 'Job is currently being processed. First three segments are active.'
      }
    }
  }
}

export const Complete: Story = {
  args: {
    state: 'complete',
  },
  parameters: {
    docs: {
      description: {
        story: 'Job has completed successfully. All segments are active.'
      }
    }
  }
}

export const Error: Story = {
  args: {
    state: 'error',
  },
  parameters: {
    docs: {
      description: {
        story: 'Job failed during processing. Shows error state in the final segment.'
      }
    }
  }
}

export const WithCustomWidth: Story = {
  args: {
    state: 'processing',
    className: 'w-[300px]'
  },
  parameters: {
    docs: {
      description: {
        story: 'The progress bar can be customized with additional classes for width or other styles.'
      }
    }
  }
} 
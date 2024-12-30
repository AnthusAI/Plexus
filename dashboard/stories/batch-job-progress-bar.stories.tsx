import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { BatchJobProgressBar } from '../components/ui/batch-job-progress-bar'

const meta: Meta<typeof BatchJobProgressBar> = {
  title: 'Components/BatchJobProgressBar',
  component: BatchJobProgressBar,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    status: {
      description: 'Current status of the batch job',
      options: ['OPEN', 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'],
      control: { type: 'radio' }
    }
  }
}

export default meta
type Story = StoryObj<typeof BatchJobProgressBar>

export const AllStates: Story = {
  render: () => (
    <div className="space-y-8 w-[600px]">
      <div>
        <div className="text-sm text-muted-foreground mb-2">OPEN - Job is created and accepting items</div>
        <BatchJobProgressBar status="OPEN" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">CLOSED - Job is closed and ready for processing</div>
        <BatchJobProgressBar status="CLOSED" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">PROCESING - Job is being processed</div>
        <BatchJobProgressBar status="PROCESSING" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">COMPLETED - Job finished successfully</div>
        <BatchJobProgressBar status="COMPLETED" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">FAILED - Job encountered an error</div>
        <BatchJobProgressBar status="ERROR" />
      </div>
    </div>
  ),
}

export const Open: Story = {
  args: {
    status: 'OPEN',
  },
  parameters: {
    docs: {
      description: {
        story: 'Initial state when the batch job is created and can accept items.'
      }
    }
  }
}

export const Closed: Story = {
  args: {
    status: 'CLOSED',
  },
  parameters: {
    docs: {
      description: {
        story: 'Job is closed and waiting to be processed.'
      }
    }
  }
}

export const Running: Story = {
  args: {
    status: 'RUNNING',
  },
  parameters: {
    docs: {
      description: {
        story: 'Job is actively processing items.'
      }
    }
  }
}

export const Completed: Story = {
  args: {
    status: 'COMPLETED',
  },
  parameters: {
    docs: {
      description: {
        story: 'Job has finished processing all items successfully.'
      }
    }
  }
}

export const Failed: Story = {
  args: {
    status: 'FAILED',
  },
  parameters: {
    docs: {
      description: {
        story: 'Job encountered an error during processing.'
      }
    }
  }
}

export const WithCustomWidth: Story = {
  args: {
    status: 'RUNNING',
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
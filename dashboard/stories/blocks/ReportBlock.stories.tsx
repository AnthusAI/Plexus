import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ReportBlock from '@/components/blocks/ReportBlock';

const meta: Meta<typeof ReportBlock> = {
  title: 'Report Blocks/ReportBlock',
  component: ReportBlock,
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof ReportBlock>;

// Sample mock files for testing
const sampleDetailsFiles = JSON.stringify([
  {
    name: 'log.txt',
    path: 'files/mock-log.txt',
    description: 'Log file for the report',
    size: 2048,
    type: 'text/plain'
  },
  {
    name: 'results.json',
    path: 'files/results.json',
    description: 'JSON results data',
    size: 4096,
    type: 'application/json'
  },
  {
    name: 'chart-data.csv',
    path: 'files/chart-data.csv',
    description: 'CSV data for charts',
    size: 3072,
    type: 'text/csv'
  }
]);

export const Basic: Story = {
  args: {
    name: 'Basic Report',
    title: 'Report Block',
    subtitle: 'Demonstration of the base report block component',
    notes: 'This example shows the common functionality that all report blocks inherit.',
    id: 'basic-report-block',
    position: 0,
    type: 'CustomReport',
    log: 'Sample log content for the report. This would typically contain execution details.',
    detailsFiles: sampleDetailsFiles,
    output: {
      someValue: 42,
      someText: 'Sample output data',
      items: [1, 2, 3, 4, 5]
    },
    config: {
      blockType: 'CustomReport',
      settings: {
        option1: true,
        option2: 'value2'
      }
    },
    children: (
      <div className="bg-card p-4 rounded-md mt-4">
        <h3 className="text-lg font-medium mb-2">Custom Report Content</h3>
        <p className="text-sm text-muted-foreground">
          Any specialized report can place its unique content here while inheriting
          standard report features like title display, log viewing, and file attachments.
        </p>
        <div className="grid grid-cols-3 gap-4 mt-4">
          <div className="bg-primary/10 p-3 rounded-md">
            <div className="text-xl font-bold">42</div>
            <div className="text-xs text-muted-foreground">Metric One</div>
          </div>
          <div className="bg-primary/10 p-3 rounded-md">
            <div className="text-xl font-bold">87%</div>
            <div className="text-xs text-muted-foreground">Metric Two</div>
          </div>
          <div className="bg-primary/10 p-3 rounded-md">
            <div className="text-xl font-bold">13.5</div>
            <div className="text-xs text-muted-foreground">Metric Three</div>
          </div>
        </div>
      </div>
    ),
  },
};

export const WithWarning: Story = {
  args: {
    ...Basic.args,
    title: 'Report With Warning',
    warning: 'This is a warning message that appears at the top of the report.',
    children: (
      <div className="bg-card p-4 rounded-md mt-4">
        <h3 className="text-lg font-medium mb-2">Report with Warning</h3>
        <p className="text-sm text-muted-foreground">
          This example demonstrates how warnings are displayed in reports.
        </p>
      </div>
    ),
  },
};

export const WithError: Story = {
  args: {
    ...Basic.args,
    title: 'Report With Error',
    error: 'This is an error message that appears at the top of the report. Errors take precedence over warnings.',
    children: (
      <div className="bg-card p-4 rounded-md mt-4">
        <h3 className="text-lg font-medium mb-2">Report with Error</h3>
        <p className="text-sm text-muted-foreground">
          This example demonstrates how errors are displayed in reports.
        </p>
      </div>
    ),
  },
};

export const WithDateRange: Story = {
  args: {
    ...Basic.args,
    title: 'Report With Date Range',
    dateRange: {
      start: '2023-01-01T00:00:00Z',
      end: '2023-03-31T23:59:59Z',
    },
    children: (
      <div className="bg-card p-4 rounded-md mt-4">
        <h3 className="text-lg font-medium mb-2">Report with Date Range</h3>
        <p className="text-sm text-muted-foreground">
          This example demonstrates how date ranges are displayed in reports.
        </p>
      </div>
    ),
  },
};

export const DefaultRenderer: Story = {
  args: {
    name: 'Default Report',
    id: 'default-report',
    position: 0,
    type: 'default',
    config: {
      option1: 'value1',
      option2: 42,
      nested: {
        key1: 'nested value',
        key2: true
      }
    },
    output: {
      result: 'success',
      data: {
        item1: 'value1',
        item2: 'value2'
      },
      metrics: [10, 20, 30, 40]
    },
  },
  parameters: {
    docs: {
      description: {
        story: 'When no children are provided, the ReportBlock falls back to showing JSON of the output and config'
      }
    }
  }
};

export const Minimal: Story = {
  args: {
    name: 'Minimal Report',
    id: 'minimal-report',
    position: 0,
    type: 'CustomReport',
    output: {},
    config: {},
    children: (
      <div className="bg-card p-4 rounded-md">
        <p className="text-sm">
          This is a minimal report with only essential properties.
        </p>
      </div>
    ),
  },
}; 
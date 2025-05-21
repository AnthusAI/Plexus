import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { BlockRenderer } from '@/components/blocks/BlockRegistry';
import TopicAnalysis from '@/components/blocks/TopicAnalysis'; // Assuming this is the component

const meta: Meta<typeof BlockRenderer> = {
  title: 'Report Blocks/TopicAnalysis',
  component: BlockRenderer, // Use BlockRenderer to test the registration
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="p-4 bg-card rounded-lg">
        <Story />
      </div>
    ),
  ],
};

export default meta;

type Story = StoryObj<typeof BlockRenderer>;

const commonOutput = {
  summary: "Topic analysis executed.",
  attached_files: [],
  skipped_files: [],
  errors: [],
};

const commonConfig = {
  class: 'TopicAnalysis',
  input_file_path: '/fake/path/to/transcripts.parquet',
  transform_method: 'chunk',
};

export const DefaultView: Story = {
  args: {
    name: 'Topic Analysis - Default',
    type: 'TopicAnalysis', // This must match TopicAnalysis.blockClass
    position: 0,
    id: 'topic-analysis-default',
    output: {
      ...commonOutput,
      summary: "Topic analysis completed successfully. No files attached yet."
    },
    config: commonConfig,
    detailsFiles: null, // No files attached initially
  },
};

export const WithAttachedFiles: Story = {
  args: {
    name: 'Topic Analysis - With Artifacts',
    type: 'TopicAnalysis',
    position: 1,
    id: 'topic-analysis-artifacts',
    output: {
      ...commonOutput,
      summary: "Topic analysis finished. 2 artifacts attached, 1 skipped.",
      attached_files: ["bertopic_plot.html", "topics.csv"],
      skipped_files: ["image.png"],
    },
    config: commonConfig,
    // Simulate what detailsFiles would look like after attachments
    detailsFiles: JSON.stringify([
      {
        name: "bertopic_plot.html",
        path: "dummy/path/bertopic_plot.html",
        type: "text/html",
        size: 12345
      },
      {
        name: "topics.csv",
        path: "dummy/path/topics.csv",
        type: "text/csv",
        size: 6789
      }
    ]),
  },
};

export const WithErrorState: Story = {
  args: {
    name: 'Topic Analysis - Error',
    type: 'TopicAnalysis',
    position: 2,
    id: 'topic-analysis-error',
    output: {
      ...commonOutput,
      summary: "Topic analysis failed during execution.",
      errors: ["Failed to process input file: File not found.", "BERTopic crashed due to memory constraints."],
      attached_files: [],
    },
    config: commonConfig,
    detailsFiles: null,
    error: "Topic analysis encountered critical errors. Check logs for details."
  },
};

export const LoadingState: Story = {
  args: {
    name: 'TopicAnalysis - Loading',
    type: 'TopicAnalysis',
    position: 3,
    id: 'topic-analysis-loading',
    output: null, // Simulate loading state for the block
    config: commonConfig,
    detailsFiles: null,
  },
};

export const TransformationOnly: Story = {
  args: {
    name: 'Topic Analysis - Transformation Only',
    type: 'TopicAnalysis',
    position: 4,
    id: 'topic-analysis-transform-only',
    output: {
      ...commonOutput,
      summary: "Transcript transformation completed, analysis skipped. No files attached.",
      transformed_text_file: "/tmp/some_transformed_text.txt"
    },
    config: {
      ...commonConfig,
      skip_analysis: true,
    },
    detailsFiles: null,
  },
}; 
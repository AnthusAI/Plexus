import type { Meta, StoryObj } from '@storybook/react';
import { CodeSnippet } from '@/components/ui/code-snippet';

const meta: Meta<typeof CodeSnippet> = {
  title: 'UI/CodeSnippet',
  component: CodeSnippet,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  argTypes: {
    type: {
      control: { type: 'select' },
      options: ['YAML', 'JSON'],
    },
    autoExpandCopy: {
      control: { type: 'boolean' },
    },
  },
};

export default meta;
type Story = StoryObj<typeof meta>;

const sampleYAMLCode = `# Topic Analysis Report Output
# 
# This is the structured output from a multi-stage topic analysis pipeline that:
# 1. Preprocesses data through programmatic filtering and preparation
# 2. Extracts content using LLM-powered transformation with custom prompts  
# 3. Discovers topics using BERTopic clustering and analysis
# 4. Fine-tunes topic representations using LLM-based naming models
#
# The output contains configuration parameters, extracted examples, discovered topics,
# visualization metadata, and file attachments from the complete analysis workflow.

summary: Topic analysis completed successfully with 3 topics identified.
preprocessing:
  method: llm
  input_file: /data/transcripts.parquet
  content_column: text
  sample_size: 1000
  customer_only: true
llm_extraction:
  method: llm_itemize
  llm_model: gpt-4o-mini
  llm_provider: openai
  examples:
    - "Customer expressed concern about pricing structure"
    - "Agent provided detailed explanation of features"
    - "Discussion about implementation timeline"
bertopic_analysis:
  num_topics_requested: null
  min_topic_size: 10
  top_n_words: 10
  min_ngram: 1
  max_ngram: 2
  skip_analysis: false
fine_tuning:
  use_representation_model: true
  representation_model_provider: openai
  representation_model_name: gpt-4o-mini
topics:
  - id: 0
    name: Pricing and Cost Concerns
    count: 245
    representation: pricing, cost, budget, expensive, affordable
    words:
      - word: pricing
        weight: 0.85
      - word: cost
        weight: 0.72
      - word: budget
        weight: 0.68
  - id: 1
    name: Feature Requests and Capabilities
    count: 189
    representation: feature, functionality, capability, integration, API
    words:
      - word: feature
        weight: 0.78
      - word: functionality
        weight: 0.65
      - word: integration
        weight: 0.61
  - id: 2
    name: Implementation and Timeline
    count: 156
    representation: implementation, timeline, deployment, rollout, schedule
    words:
      - word: implementation
        weight: 0.82
      - word: timeline
        weight: 0.74
      - word: deployment
        weight: 0.69`;

const sampleJSONCode = `{
  "summary": "Feedback analysis completed with 3 scores analyzed.",
  "overall_ac1": 0.847,
  "date_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  },
  "scores": [
    {
      "score_id": "grammar-check",
      "score_name": "Grammar Check",
      "agreement_score": 0.923,
      "total_feedback_items": 156,
      "statistics": {
        "precision": 0.89,
        "recall": 0.94,
        "f1_score": 0.91
      },
      "confusion_matrix": {
        "true_positive": 87,
        "false_positive": 12,
        "true_negative": 45,
        "false_negative": 12
      }
    },
    {
      "score_id": "sentiment-analysis",
      "score_name": "Sentiment Analysis",
      "agreement_score": 0.776,
      "total_feedback_items": 203,
      "statistics": {
        "precision": 0.82,
        "recall": 0.78,
        "f1_score": 0.80
      }
    }
  ]
}`;

export const YAMLDefault: Story = {
  args: {
    code: sampleYAMLCode,
    type: 'YAML',
    autoExpandCopy: true,
  },
};

export const YAMLWithCustomTitle: Story = {
  args: {
    code: sampleYAMLCode,
    type: 'YAML',
    title: 'Topic Analysis Results',
    description: 'Complete topic analysis output with discovered patterns and insights',
    autoExpandCopy: true,
  },
};

export const JSONLegacy: Story = {
  args: {
    code: sampleJSONCode,
    type: 'JSON',
    title: 'Legacy Feedback Analysis',
    description: 'Legacy JSON code output from the report block execution',
    autoExpandCopy: false,
  },
};

export const JSONCompact: Story = {
  args: {
    code: '{"status": "success", "message": "Task completed", "data": {"items": 42}}',
    type: 'JSON',
    autoExpandCopy: true,
  },
};

export const YAMLSimple: Story = {
  args: {
    code: `# Simple Configuration Example
name: My Configuration
enabled: true
settings:
  debug: false
  timeout: 30
  features:
    - analytics
    - notifications
    - reporting`,
    type: 'YAML',
    title: 'Configuration File',
    description: 'Simple YAML configuration that can be copied and modified',
    autoExpandCopy: true,
  },
};

export const NoAutoExpandCopy: Story = {
  args: {
    code: sampleYAMLCode,
    type: 'YAML',
    title: 'Manual Copy Only',
    description: 'This example requires manual copy button click',
    autoExpandCopy: false,
  },
};

export const CustomStyling: Story = {
  args: {
    code: sampleYAMLCode,
    type: 'YAML',
    className: 'max-w-2xl mx-auto shadow-lg',
    autoExpandCopy: true,
  },
};
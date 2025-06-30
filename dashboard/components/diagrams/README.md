# Topic Analysis Diagram with Template Variables

This directory contains components for displaying the Topic Analysis Pipeline diagram with support for Jinja2-style template variable interpolation.

## Components

### `TopicAnalysisViewer`
A React component that displays the topic analysis diagram with customizable template variables.

```tsx
import { TopicAnalysisViewer } from '@/components/diagrams';

// Basic usage with default "TEST TEST" values
<TopicAnalysisViewer />

// With custom variables
<TopicAnalysisViewer
  variables={{
    preprocessor: "Custom Preprocessor",
    LLM: "GPT-4",
    BERTopic: "BERTopic v0.15",
    finetune: "LoRA Fine-tuning"
  }}
  height={600}
/>
```

### `TopicAnalysisExample`
A complete example component with input fields to dynamically change the template variables.

```tsx
import { TopicAnalysisExample } from '@/components/diagrams';

<TopicAnalysisExample />
```

### `TopicAnalysisDemo`
A demonstration component showing how real analysis configuration data is extracted and displayed in the diagram.

```tsx
import { TopicAnalysisDemo } from '@/components/diagrams';

<TopicAnalysisDemo />
```

### Real-world Usage in TopicAnalysis Component
The `TopicAnalysis` component automatically extracts configuration details from analysis data:

```tsx
// Automatically extracts configuration from analysis data
const getDiagramVariables = (): TemplateVariables => {
  return {
    preprocessor: preprocessing.method 
      ? `${preprocessing.method} (${preprocessing.sample_size?.toLocaleString()} samples)` 
      : 'Standard preprocessing',
    LLM: llmExtraction.llm_model 
      ? `${llmExtraction.llm_provider}: ${llmExtraction.llm_model}` 
      : 'LLM extraction',
    BERTopic: `BERTopic (min: ${bertopicAnalysis.min_topic_size}, topics: ${bertopicAnalysis.num_topics_requested})`,
    finetune: fineTuning.use_representation_model 
      ? `${fineTuning.representation_model_provider}: ${fineTuning.representation_model_name}` 
      : 'No fine-tuning'
  };
};

<TopicAnalysisViewer variables={getDiagramVariables()} />
```

## Template Variables

The following Jinja2-style variables are supported in the diagram:

- `{{preprocessor}}` - Name/description of the preprocessing step
- `{{LLM}}` - Name of the Large Language Model used
- `{{BERTopic}}` - BERTopic configuration or version
- `{{finetune}}` - Fine-tuning method or configuration

### Text Formatting for Narrow Columns

The diagram displays text in narrow vertical columns. To ensure proper formatting, the template variables should include `\n` line breaks to create vertical text layout:

```tsx
// Example formatted variables
{
  preprocessor: "itemize\n10,000\nsamples",
  LLM: "OpenAI\ngpt\n4o\nmini", 
  BERTopic: "BERTopic\nmin: 10\ntopics: 15\n1-2gram",
  finetune: "OpenAI\ngpt\n4o\nmini"
}
```

## Functions

### `createTopicAnalysisPipelineDiagram(variables)`
Creates a diagram data object with interpolated template variables.

```tsx
import { createTopicAnalysisPipelineDiagram } from '@/components/diagrams';

const diagramData = createTopicAnalysisPipelineDiagram({
  preprocessor: "Text Cleaning",
  LLM: "Claude-3",
  BERTopic: "BERTopic v0.15",
  finetune: "QLoRA"
});
```

## Default Values

When no variables are provided, all template variables default to "TEST TEST" as requested.

## Text Formatting Utilities

The package includes utility functions to help format text for narrow diagram columns:

```tsx
import { 
  formatPreprocessor, 
  formatLLM, 
  formatBERTopic, 
  formatFineTuning,
  formatModelName,
  formatForNarrowColumn 
} from '@/components/diagrams';

// Format individual components
const preprocessor = formatPreprocessor('itemize', 10000); // "itemize\n10K\nsamples"
const llm = formatLLM('OpenAI', 'gpt-4o-mini'); // "OpenAI\ngpt\n4o\nmini"
const bertopic = formatBERTopic({ minTopicSize: 10, requestedTopics: 15 }); // "BERTopic\nmin: 10\ntopics: 15"
const finetune = formatFineTuning({ useRepresentationModel: true, provider: 'OpenAI', model: 'gpt-4o-mini' });
```

## File Structure

- `topic-analysis-pipeline.json` - Original Excalidraw diagram with `{{variables}}`
- `topic-analysis-diagram.ts` - Core templating logic and diagram data
- `topic-analysis-viewer.tsx` - React component for displaying the diagram
- `topic-analysis-example.tsx` - Example component with interactive inputs
- `topic-analysis-demo.tsx` - Real-world demonstration component
- `text-formatting-utils.ts` - Utility functions for formatting text in narrow columns
- `excalidraw-viewer.tsx` - Base Excalidraw viewer component
- `index.ts` - Exports all components and utilities 
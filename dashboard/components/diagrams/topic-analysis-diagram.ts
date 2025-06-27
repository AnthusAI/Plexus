// Topic Analysis Pipeline Diagram Data
// This loads the actual Excalidraw diagram showing Pre-filtering + LLM itemization + BERTopic + LLM fine-tuning

import diagramData from './topic-analysis-pipeline.json';

// Template variables interface
interface TemplateVariables {
  preprocessor?: string;
  LLM?: string;
  BERTopic?: string;
  finetune?: string;
}

// Function to interpolate template variables in the diagram data
function interpolateTemplate(data: any, variables: TemplateVariables): any {
  // Deep clone the data to avoid modifying the original
  const clonedData = JSON.parse(JSON.stringify(data));
  
  // Recursively traverse and replace template variables
  function replaceInObject(obj: any): any {
    if (typeof obj === 'string') {
      return obj
        .replace(/\{\{preprocessor\}\}/g, variables.preprocessor || '{{preprocessor}}')
        .replace(/\{\{LLM\}\}/g, variables.LLM || '{{LLM}}')
        .replace(/\{\{BERTopic\}\}/g, variables.BERTopic || '{{BERTopic}}')
        .replace(/\{\{finetune\}\}/g, variables.finetune || '{{finetune}}');
    } else if (Array.isArray(obj)) {
      return obj.map(replaceInObject);
    } else if (obj && typeof obj === 'object') {
      const result: any = {};
      for (const [key, value] of Object.entries(obj)) {
        result[key] = replaceInObject(value);
      }
      return result;
    }
    return obj;
  }
  
  return replaceInObject(clonedData);
}

// Function to create diagram with template variables
export function createTopicAnalysisPipelineDiagram(variables: TemplateVariables = {}) {
  const interpolatedData = interpolateTemplate(diagramData, variables);
  
  return {
    elements: interpolatedData.elements,
    appState: {
      ...interpolatedData.appState,
      viewBackgroundColor: "#ffffff",
      gridSize: null,
      scrollX: ((interpolatedData.appState as any).scrollX || 0),
      scrollY: ((interpolatedData.appState as any).scrollY || 0),
      zoom: {
        value: 0.6, // Good zoom for dashboard embedding
      },
    },
  };
}

// Default export with "TEST TEST" values as requested
export const topicAnalysisPipelineDiagram = createTopicAnalysisPipelineDiagram({
  preprocessor: "TEST TEST",
  LLM: "TEST TEST", 
  BERTopic: "TEST TEST",
  finetune: "TEST TEST"
});

// Export the template variables interface for use in other components
export type { TemplateVariables }; 
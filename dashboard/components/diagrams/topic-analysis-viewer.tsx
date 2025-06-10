import React from 'react';
import ExcalidrawViewer from './excalidraw-viewer';
import { createTopicAnalysisPipelineDiagram, TemplateVariables } from './topic-analysis-diagram';

interface TopicAnalysisViewerProps {
  variables?: TemplateVariables;
  viewModeEnabled?: boolean;
  width?: string | number;
  height?: string | number;
  className?: string;
}

const TopicAnalysisViewer: React.FC<TopicAnalysisViewerProps> = ({
  variables = {
    preprocessor: "TEST TEST",
    LLM: "TEST TEST",
    BERTopic: "TEST TEST",
    finetune: "TEST TEST"
  },
  viewModeEnabled = true,
  width = "100%",
  height = 600,
  className = ""
}) => {
  // Generate the diagram data with interpolated variables
  const diagramData = createTopicAnalysisPipelineDiagram(variables);

  return (
    <ExcalidrawViewer
      initialData={diagramData}
      viewModeEnabled={viewModeEnabled}
      width={width}
      height={height}
      className={className}
    />
  );
};

export default TopicAnalysisViewer; 
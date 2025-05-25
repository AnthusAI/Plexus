import React from 'react';
import ReportBlock, { ReportBlockProps } from './ReportBlock'; // Corrected import

/**
 * Placeholder component for Topic Analysis.
 * Currently, it renders a generic message and relies on DefaultReportBlock
 * or the BlockRenderer's capabilities to display attached files.
 */
const TopicAnalysis: React.FC<ReportBlockProps> = (props) => {
  // Debug logging to see what we're receiving
  console.log('🔍 TopicAnalysis component received props:', {
    hasOutput: !!props.output,
    outputKeys: props.output ? Object.keys(props.output) : 'none',
    name: props.name,
    type: props.type,
    hasAttachedFiles: !!props.attachedFiles,
    attachedFilesLength: props.attachedFiles?.length || 0
  });

  if (!props.output) {
    console.log('❌ TopicAnalysis: No output data, showing loading message');
    return <p>Topic analysis data is loading or not available.</p>;
  }

  console.log('✅ TopicAnalysis: Rendering ReportBlock with output:', props.output);
  
  // Use the imported ReportBlock (which is the default export from ReportBlock.tsx)
  // and pass down all props.
  return (
    <ReportBlock {...props} />
  );
};

// Set the blockClass property for the registry
(TopicAnalysis as any).blockClass = 'TopicAnalysis';

export default TopicAnalysis; 
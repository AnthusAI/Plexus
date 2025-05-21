import React from 'react';
import ReportBlock, { ReportBlockProps } from './ReportBlock'; // Corrected import

/**
 * Placeholder component for Topic Analysis.
 * Currently, it renders a generic message and relies on DefaultReportBlock
 * or the BlockRenderer's capabilities to display attached files.
 */
const TopicAnalysis: React.FC<ReportBlockProps> = (props) => {
  // For now, TopicAnalysis will display a simple message and let the
  // default block rendering handle the display of `detailsFiles`.
  // We can enhance this component later to display specific visualizations
  // if the output structure of the Python block evolves.

  // You can use the props like props.name, props.output, props.log, props.config
  // props.detailsFiles should be available if files were attached.

  if (!props.output) {
    return <p>Topic analysis data is loading or not available.</p>;
  }

  // Use the imported ReportBlock (which is the default export from ReportBlock.tsx)
  // and pass down all props.
  return (
    <ReportBlock {...props} />
  );
};

// Set the blockClass property for the registry
(TopicAnalysis as any).blockClass = 'TopicAnalysis';

export default TopicAnalysis; 
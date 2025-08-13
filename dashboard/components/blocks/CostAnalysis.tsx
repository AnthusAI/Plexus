import React from 'react';
import { ReportBlockProps } from './ReportBlock';
import { CostAnalysisDisplay, type CostAnalysisDisplayData } from '@/components/ui/cost-analysis-display';
import * as yaml from 'js-yaml';

export interface CostAnalysisData extends CostAnalysisDisplayData {}

const CostAnalysis: React.FC<ReportBlockProps> = (props) => {
  if (!props.output) {
    return <p>No cost analysis data available or data is loading.</p>;
  }

  let data: CostAnalysisData;
  try {
    if (typeof props.output === 'string') {
      data = yaml.load(props.output) as CostAnalysisData;
    } else {
      data = props.output as CostAnalysisData;
    }
  } catch (error) {
    console.error('❌ CostAnalysis: Failed to parse output data:', error);
    return (
      <div className="p-4 text-center text-destructive">
        Error parsing cost analysis data. Please check the report generation.
      </div>
    );
  }

  const title = (props.name && !props.name.startsWith('block_')) ? props.name : 'Cost Analysis';

  return (
    <CostAnalysisDisplay
      data={data}
      title={title}
      subtitle={data.block_description}
      attachedFiles={props.attachedFiles}
      log={props.log}
      rawOutput={typeof props.output === 'string' ? props.output : undefined}
      id={props.id}
      position={props.position}
      config={props.config}
    />
  );
};

(CostAnalysis as any).blockClass = 'CostAnalysis';

export default CostAnalysis;




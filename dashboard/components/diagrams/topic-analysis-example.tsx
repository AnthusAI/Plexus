import React, { useState } from 'react';
import TopicAnalysisViewer from './topic-analysis-viewer';
import { TemplateVariables } from './topic-analysis-diagram';

const TopicAnalysisExample: React.FC = () => {
  const [variables, setVariables] = useState<TemplateVariables>({
    preprocessor: "TEST TEST",
    LLM: "TEST TEST",
    BERTopic: "TEST TEST",
    finetune: "TEST TEST"
  });

  const handleVariableChange = (key: keyof TemplateVariables, value: string) => {
    setVariables(prev => ({
      ...prev,
      [key]: value
    }));
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-2">Preprocessor</label>
          <input
            type="text"
            value={variables.preprocessor || ''}
            onChange={(e) => handleVariableChange('preprocessor', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter preprocessor name"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">LLM</label>
          <input
            type="text"
            value={variables.LLM || ''}
            onChange={(e) => handleVariableChange('LLM', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter LLM name"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">BERTopic</label>
          <input
            type="text"
            value={variables.BERTopic || ''}
            onChange={(e) => handleVariableChange('BERTopic', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter BERTopic configuration"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">Fine-tune</label>
          <input
            type="text"
            value={variables.finetune || ''}
            onChange={(e) => handleVariableChange('finetune', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Enter fine-tune configuration"
          />
        </div>
      </div>
      
      <div className="border rounded-lg p-4">
        <h3 className="text-lg font-semibold mb-4">Topic Analysis Pipeline</h3>
        <TopicAnalysisViewer
          variables={variables}
          height={600}
          className="border rounded"
        />
      </div>
    </div>
  );
};

export default TopicAnalysisExample; 
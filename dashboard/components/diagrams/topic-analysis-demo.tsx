import React from 'react';
import TopicAnalysisViewer from './topic-analysis-viewer';
import { TemplateVariables } from './topic-analysis-diagram';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

// Example analysis data structure (similar to what TopicAnalysis component receives)
const exampleAnalysisData = {
  preprocessing: {
    method: "itemize",
    sample_size: 10000,
    customer_only: true,
    steps: [
      { step: 1, class: "TextCleaner", parameters: { remove_html: true } },
      { step: 2, class: "Deduplicator", parameters: { threshold: 0.9 } }
    ]
  },
  llm_extraction: {
    llm_provider: "OpenAI",
    llm_model: "gpt-4o-mini",
    method: "structured_extraction"
  },
  bertopic_analysis: {
    min_topic_size: 10,
    num_topics_requested: 15,
    min_ngram: 1,
    max_ngram: 2,
    top_n_words: 10
  },
  fine_tuning: {
    use_representation_model: true,
    representation_model_provider: "OpenAI",
    representation_model_name: "gpt-4o-mini"
  }
};

// Function that mimics the extraction logic from TopicAnalysis component
const extractDiagramVariables = (data: typeof exampleAnalysisData): TemplateVariables => {
  const { preprocessing, llm_extraction, bertopic_analysis, fine_tuning } = data;

  // Preprocessing summary - format for narrow column
  const method = preprocessing.method || 'Standard';
  const sampleSize = preprocessing.sample_size;
  
  let preprocessorSummary = method;
  if (sampleSize) {
    preprocessorSummary += `\n${sampleSize.toLocaleString()}\nsamples`;
  }

  // LLM summary - format for narrow column
  const provider = llm_extraction.llm_provider || 'LLM';
  const model = llm_extraction.llm_model;
  
  let llmSummary = provider;
  if (model) {
    // Split long model names
    const modelParts = model.split('-');
    if (modelParts.length > 1) {
      llmSummary += `\n${modelParts.join('\n')}`;
    } else {
      llmSummary += `\n${model}`;
    }
  } else {
    llmSummary += '\nextraction';
  }

  // BERTopic summary - format for narrow column
  let bertopicSummary = 'BERTopic';
  const minTopicSize = bertopic_analysis.min_topic_size;
  const requestedTopics = bertopic_analysis.num_topics_requested;
  const minNgram = bertopic_analysis.min_ngram;
  const maxNgram = bertopic_analysis.max_ngram;
  
  if (minTopicSize) {
    bertopicSummary += `\nmin: ${minTopicSize}`;
  }
  if (requestedTopics) {
    bertopicSummary += `\ntopics: ${requestedTopics}`;
  }
  if (minNgram && maxNgram) {
    bertopicSummary += `\n${minNgram}-${maxNgram}gram`;
  }

  // Fine-tuning summary - format for narrow column
  let finetuneSummary = 'No\nfine-tuning';
  if (fine_tuning.use_representation_model) {
    const ftProvider = fine_tuning.representation_model_provider || 'LLM';
    const ftModel = fine_tuning.representation_model_name;
    
    finetuneSummary = ftProvider;
    if (ftModel) {
      // Split long model names
      const ftModelParts = ftModel.split('-');
      if (ftModelParts.length > 1) {
        finetuneSummary += `\n${ftModelParts.join('\n')}`;
      } else {
        finetuneSummary += `\n${ftModel}`;
      }
    } else {
      finetuneSummary += '\nfine-tuning';
    }
  }

  return {
    preprocessor: preprocessorSummary,
    LLM: llmSummary,
    BERTopic: bertopicSummary,
    finetune: finetuneSummary
  };
};

const TopicAnalysisDemo: React.FC = () => {
  const variables = extractDiagramVariables(exampleAnalysisData);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Configuration Data */}
        <Card>
          <CardHeader>
            <CardTitle>Example Analysis Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h4 className="font-medium mb-2">Preprocessing</h4>
              <div className="text-sm space-y-1">
                <div>Method: <code>{exampleAnalysisData.preprocessing.method}</code></div>
                <div>Sample Size: <code>{exampleAnalysisData.preprocessing.sample_size?.toLocaleString()}</code></div>
                <div>Customer Only: <code>{exampleAnalysisData.preprocessing.customer_only ? 'Yes' : 'No'}</code></div>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">LLM Extraction</h4>
              <div className="text-sm space-y-1">
                <div>Provider: <code>{exampleAnalysisData.llm_extraction.llm_provider}</code></div>
                <div>Model: <code>{exampleAnalysisData.llm_extraction.llm_model}</code></div>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">BERTopic Analysis</h4>
              <div className="text-sm space-y-1">
                <div>Min Topic Size: <code>{exampleAnalysisData.bertopic_analysis.min_topic_size}</code></div>
                <div>Requested Topics: <code>{exampleAnalysisData.bertopic_analysis.num_topics_requested}</code></div>
                <div>N-gram Range: <code>{exampleAnalysisData.bertopic_analysis.min_ngram}-{exampleAnalysisData.bertopic_analysis.max_ngram}</code></div>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium mb-2">Fine-tuning</h4>
              <div className="text-sm space-y-1">
                <div>Use Representation Model: <code>{exampleAnalysisData.fine_tuning.use_representation_model ? 'Yes' : 'No'}</code></div>
                <div>Provider: <code>{exampleAnalysisData.fine_tuning.representation_model_provider}</code></div>
                <div>Model: <code>{exampleAnalysisData.fine_tuning.representation_model_name}</code></div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Extracted Variables */}
        <Card>
          <CardHeader>
            <CardTitle>Extracted Diagram Variables</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <span className="font-medium">Preprocessor:</span>
              <div className="text-sm bg-muted p-2 rounded mt-1 font-mono whitespace-pre-line">
                {variables.preprocessor}
              </div>
            </div>
            <div>
              <span className="font-medium">LLM:</span>
              <div className="text-sm bg-muted p-2 rounded mt-1 font-mono whitespace-pre-line">
                {variables.LLM}
              </div>
            </div>
            <div>
              <span className="font-medium">BERTopic:</span>
              <div className="text-sm bg-muted p-2 rounded mt-1 font-mono whitespace-pre-line">
                {variables.BERTopic}
              </div>
            </div>
            <div>
              <span className="font-medium">Fine-tune:</span>
              <div className="text-sm bg-muted p-2 rounded mt-1 font-mono whitespace-pre-line">
                {variables.finetune}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Dynamic Diagram */}
      <Card>
        <CardHeader>
          <CardTitle>Dynamic Topic Analysis Pipeline</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <TopicAnalysisViewer
            variables={variables}
            height={600}
            className="rounded-lg"
          />
        </CardContent>
      </Card>
    </div>
  );
};

export default TopicAnalysisDemo; 
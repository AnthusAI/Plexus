import React, { useState } from 'react';
import { ReportBlockProps } from './ReportBlock';
import ReportBlock from './ReportBlock';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown, ChevronRight, Eye, EyeOff, MessagesSquare } from 'lucide-react';
import * as yaml from 'js-yaml';

interface TopicAnalysisData {
  summary?: string;
  transformed_text_file?: string;
  skipped_files?: string[];
  preprocessing?: {
    method?: string;
    input_file?: string;
    original_input_file?: string;
    content_column?: string;
    sample_size?: number;
    customer_only?: boolean;
    preprocessed_rows?: number;
    steps?: Array<{
      step: number;
      class: string;
      parameters: Record<string, any>;
    }>;
  };
  llm_extraction?: {
    llm_model?: string;
    method?: string;
    prompt_used?: string;
    examples?: string[];
    llm_provider?: string;
  };
  bertopic_analysis?: {
    num_topics_requested?: number;
    min_topic_size?: number;
    top_n_words?: number;
    min_ngram?: number;
    max_ngram?: number;
    skip_analysis?: boolean;
  };
  fine_tuning?: {
    use_representation_model?: boolean;
    representation_model_provider?: string;
    representation_model_name?: string;
  };
  topics?: Array<{
    id: number;
    name: string;
    count: number;
    representation: string;
    words: Array<{ word: string; weight: number }>;
  }>;
  visualization_notes?: {
    topics_visualization?: string;
    heatmap_visualization?: string;
    available_files?: string;
  };
  debug_info?: {
    transformed_text_lines_count?: number;
    transformed_text_sample?: string[];
    unique_lines_count?: number;
    repetition_detected?: boolean;
    most_common_lines?: Array<{
      line: string;
      count: number;
    }>;
    error_reading_transformed_file?: string;
  };
  block_title?: string;
  errors?: string[];
}

/**
 * Topic Analysis Report Block Component
 * 
 * Displays a comprehensive topic analysis report with sections for:
 * - Pre-processing
 * - LLM Extraction 
 * - BERTopic Analysis
 * - Fine-tuning
 */

const TopicAnalysis: React.FC<ReportBlockProps> = (props) => {
  const [promptExpanded, setPromptExpanded] = useState(false);
  const [examplesExpanded, setExamplesExpanded] = useState(false);
  
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
    return (
      <div className="p-4 text-center text-muted-foreground">
        Topic analysis data is loading or not available.
      </div>
    );
  }

  // Parse YAML if output is string, otherwise use as object (legacy support)
  let data: TopicAnalysisData;
  try {
    if (typeof props.output === 'string') {
      console.log('🔍 TopicAnalysis: Parsing YAML string output, first 1000 chars:', props.output.substring(0, 1000));
      // New format: parse YAML string
      const parsedData = yaml.load(props.output);
      console.log('🔍 TopicAnalysis: Parsed YAML data:', parsedData);
      console.log('🔍 TopicAnalysis: Topics in parsed data:', (parsedData as any)?.topics);
      console.log('🔍 TopicAnalysis: Type of topics:', typeof (parsedData as any)?.topics);
      console.log('🔍 TopicAnalysis: Is topics array?', Array.isArray((parsedData as any)?.topics));
      if ((parsedData as any)?.topics) {
        console.log('🔍 TopicAnalysis: Topics length:', (parsedData as any).topics.length);
        console.log('🔍 TopicAnalysis: First topic:', (parsedData as any).topics[0]);
      }
      data = parsedData as TopicAnalysisData;
    } else {
      console.log('🔍 TopicAnalysis: Using object output directly:', props.output);
      // Legacy format: use object directly
      data = props.output as TopicAnalysisData;
    }
  } catch (error) {
    console.error('❌ TopicAnalysis: Failed to parse output data:', error);
    console.error('❌ TopicAnalysis: Raw output that failed to parse:', props.output);
    return (
      <div className="p-4 text-center text-destructive">
        Error parsing topic analysis data. Please check the report generation.
      </div>
    );
  }
  const preprocessing = data.preprocessing || {};
  const llmExtraction = data.llm_extraction || {};
  const bertopicAnalysis = data.bertopic_analysis || {};
  const fineTuning = data.fine_tuning || {};
  const topics = data.topics || [];
  const errors = data.errors || [];

  console.log('✅ TopicAnalysis: Rendering with structured data:', {
    hasTopics: !!data.topics,
    topicsLength: data.topics?.length || 0,
    topicsData: data.topics,
    topicsIsArray: Array.isArray(data.topics),
    topicsType: typeof data.topics,
    summary: data.summary,
    block_title: data.block_title,
    allDataKeys: Object.keys(data)
  });
  
  // Additional debugging for topics specifically
  console.log('🔍 TopicAnalysis: Topics debugging:', {
    originalTopics: data.topics,
    extractedTopics: topics,
    topicsLength: topics.length,
    firstTopic: topics[0],
    topicsArrayCheck: Array.isArray(topics)
  });

  return (
    <ReportBlock {...props}>
      {/* Custom Topic Analysis Content */}
      <div className="mt-6 space-y-6">
        {errors.length > 0 && (
          <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
            <h4 className="text-sm font-medium text-destructive mb-1">Errors:</h4>
            <ul className="text-sm text-destructive space-y-1">
              {errors.map((error, i) => (
                <li key={i}>• {error}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Main Topic Analysis Results */}
        <TopicAnalysisResults topics={topics} />

        {/* Process Details Sections */}
        <Accordion type="multiple" defaultValue={["llm-extraction"]} className="w-full">
          {/* Pre-processing Section */}
          <AccordionItem value="preprocessing">
            <AccordionTrigger className="text-base font-medium">
              Pre-processing
              <div className="ml-2 px-2 py-1 text-xs bg-card rounded">
                {preprocessing.method || 'itemize'}
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <PreprocessingSection preprocessing={preprocessing} />
            </AccordionContent>
          </AccordionItem>

          {/* LLM Extraction Section */}
          <AccordionItem value="llm-extraction">
            <AccordionTrigger className="text-base font-medium">
              LLM Extraction
              {llmExtraction.examples && (
                <div className="ml-2 px-2 py-1 text-xs bg-card rounded">
                  {llmExtraction.examples.length} examples
                </div>
              )}
            </AccordionTrigger>
            <AccordionContent>
              <LLMExtractionSection 
                llmExtraction={llmExtraction}
                promptExpanded={promptExpanded}
                setPromptExpanded={setPromptExpanded}
                examplesExpanded={examplesExpanded}
                setExamplesExpanded={setExamplesExpanded}
              />
            </AccordionContent>
          </AccordionItem>

          {/* BERTopic Analysis Section */}
          <AccordionItem value="bertopic">
            <AccordionTrigger className="text-base font-medium">
              BERTopic Analysis
              {topics.length > 0 && (
                <div className="ml-2 px-2 py-1 text-xs bg-card rounded">
                  {topics.length} topics
                </div>
              )}
            </AccordionTrigger>
            <AccordionContent>
              <BERTopicSection 
                topics={topics}
                bertopicAnalysis={bertopicAnalysis}
                visualizationNotes={data.visualization_notes}
                attachedFiles={props.attachedFiles || undefined}
              />
            </AccordionContent>
          </AccordionItem>

          {/* Fine-tuning Section */}
          <AccordionItem value="fine-tuning">
            <AccordionTrigger className="text-base font-medium">
              Fine-tuning
              {fineTuning.representation_model_provider && (
                <div className="ml-2 px-2 py-1 text-xs bg-card rounded">
                  {fineTuning.representation_model_name || fineTuning.representation_model_provider}
                </div>
              )}
            </AccordionTrigger>
            <AccordionContent>
              <FineTuningSection 
                fineTuning={fineTuning}
                topics={topics}
              />
            </AccordionContent>
          </AccordionItem>

          {/* Debug Information Section */}
          {data.debug_info && (
            <AccordionItem value="debug-info">
              <AccordionTrigger className="text-base font-medium">
                Debug Information
                {data.debug_info.repetition_detected && (
                  <Badge variant="destructive" className="ml-2">
                    Repetition Detected
                  </Badge>
                )}
              </AccordionTrigger>
              <AccordionContent>
                <DebugInfoSection debugInfo={data.debug_info} />
              </AccordionContent>
            </AccordionItem>
          )}
        </Accordion>
      </div>
    </ReportBlock>
  );
};

/**
 * Main Topic Analysis Results Section
 * Shows the discovered topics as the primary output
 */
const TopicAnalysisResults: React.FC<{
  topics: Array<{
    id: number;
    name: string;
    count: number;
    representation: string;
    words: Array<{ word: string; weight: number }>;
  }>;
}> = ({ topics }) => {
  if (topics.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <MessagesSquare className="h-5 w-5" />
          <h3 className="text-lg font-medium">Topic Analysis Results</h3>
        </div>
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base text-muted-foreground">Analyzing topics...</CardTitle>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted border-t-foreground"></div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="h-4 bg-muted rounded animate-pulse w-3/4"></div>
                <div className="space-y-2">
                  <div className="flex flex-wrap gap-1">
                    {[1, 2, 3, 4, 5, 6].map((j) => (
                      <div key={j} className="h-6 bg-muted rounded animate-pulse w-16"></div>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessagesSquare className="h-5 w-5" />
          <h3 className="text-lg font-medium">Topic Analysis Results</h3>
        </div>
        <span className="text-sm text-muted-foreground">{topics.length} topics discovered</span>
      </div>
      
      <div className="space-y-4">
        {topics.map((topic) => (
          <Card key={topic.id}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Topic {topic.id}</CardTitle>
                <span className="text-sm text-muted-foreground">{topic.count} items</span>
              </div>
            </CardHeader>
            <CardContent>
              <h4 className="font-medium mb-2">{topic.name}</h4>
              {topic.words && topic.words.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Key Terms</p>
                  <div className="flex flex-wrap gap-1">
                    {topic.words.slice(0, 6).map((word, i) => (
                      <Badge key={i} variant="outline" className="text-xs font-mono">
                        {word.word}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

/**
 * Preprocessing Section Component
 * Shows programmatic data preparation steps
 */
const PreprocessingSection: React.FC<{
  preprocessing: any;
}> = ({ preprocessing }) => {
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-muted-foreground">
        Programmatic data preparation and filtering steps performed before LLM processing.
      </p>
      
      <div className="grid gap-3">
        {preprocessing.method && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Transform Method:</span>
            <Badge variant="secondary">{preprocessing.method}</Badge>
          </div>
        )}
        {(preprocessing.input_file || preprocessing.original_input_file) && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Input File:</span>
            <span className="text-sm text-muted-foreground font-mono">
              {(preprocessing.original_input_file || preprocessing.input_file)?.split('/').pop()}
            </span>
          </div>
        )}
        {preprocessing.preprocessed_rows && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Preprocessed Rows:</span>
            <Badge variant="outline">{preprocessing.preprocessed_rows.toLocaleString()}</Badge>
          </div>
        )}
        {preprocessing.content_column && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Content Column:</span>
            <span className="text-sm text-muted-foreground font-mono">
              {preprocessing.content_column}
            </span>
          </div>
        )}
        {preprocessing.sample_size && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Sample Size:</span>
            <Badge variant="outline">{preprocessing.sample_size}</Badge>
          </div>
        )}
        {typeof preprocessing.customer_only === 'boolean' && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Customer Only:</span>
            <Badge variant={preprocessing.customer_only ? "default" : "secondary"}>
              {preprocessing.customer_only ? "Yes" : "No"}
            </Badge>
          </div>
        )}
      </div>
      
      {/* Preprocessing Steps */}
      {preprocessing.steps && preprocessing.steps.length > 0 && (
        <div className="space-y-3 mt-4">
          <h4 className="font-medium text-sm">Preprocessing Steps Applied</h4>
          <div className="space-y-2">
            {preprocessing.steps.map((step: { step: number; class: string; parameters: Record<string, any> }, index: number) => (
              <div key={index} className="flex items-center justify-between p-2 border rounded-md bg-muted/20">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">
                    {step.step}
                  </Badge>
                  <span className="text-sm font-medium">{step.class}</span>
                </div>
                {Object.keys(step.parameters).length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(step.parameters).map(([key, value]) => (
                      <Badge key={key} variant="secondary" className="text-xs">
                        {key}: {String(value)}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * LLM Extraction Section Component
 * Displays the prompt and extracted examples with collapsible/expandable sections
 */
const LLMExtractionSection: React.FC<{
  llmExtraction: any;
  promptExpanded: boolean;
  setPromptExpanded: (expanded: boolean) => void;
  examplesExpanded: boolean;
  setExamplesExpanded: (expanded: boolean) => void;
}> = ({ llmExtraction, promptExpanded, setPromptExpanded, examplesExpanded, setExamplesExpanded }) => {
  const [selectedExamples, setSelectedExamples] = useState<Set<number>>(new Set());
  const [showAllExamples, setShowAllExamples] = useState(false);
  
  const examples = llmExtraction.examples || [];
  const displayedExamples = showAllExamples ? examples : examples.slice(0, 5);
  
  const toggleExampleSelection = (index: number) => {
    const newSelection = new Set(selectedExamples);
    if (newSelection.has(index)) {
      newSelection.delete(index);
    } else {
      newSelection.add(index);
    }
    setSelectedExamples(newSelection);
  };

  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-muted-foreground">
        LLM-powered text extraction and transformation using structured prompts.
      </p>
      
      {/* Model Info */}
      <div className="space-y-2">
        {llmExtraction.llm_provider && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Provider:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">
              {llmExtraction.llm_provider}
            </div>
          </div>
        )}
        {llmExtraction.llm_model && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Model:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">
              {llmExtraction.llm_model}
            </div>
          </div>
        )}
      </div>

      {/* Extraction Prompt Section */}
      {llmExtraction.prompt_used && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Extraction Prompt:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">
              {llmExtraction.prompt_used.length} chars
            </div>
          </div>
          <Collapsible open={promptExpanded} onOpenChange={setPromptExpanded}>
            <CollapsibleTrigger asChild>
              <Button 
                variant="ghost" 
                size="sm"
                className="justify-start gap-2 p-0 h-auto font-normal"
              >
                {promptExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                <span className="text-sm text-muted-foreground">Show prompt</span>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-2">
                <pre className="text-xs bg-muted p-3 rounded overflow-x-auto whitespace-pre-wrap">
                  {llmExtraction.prompt_used}
                </pre>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>
      )}

      {/* Examples Section */}
      {examples.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="font-medium">Extraction Examples</h4>
            <div className="flex items-center gap-2">
              {selectedExamples.size > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedExamples(new Set())}
                >
                  Clear ({selectedExamples.size})
                </Button>
              )}
              {examples.length > 5 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowAllExamples(!showAllExamples)}
                >
                  {showAllExamples ? `Show Less` : `Show All (${examples.length})`}
                </Button>
              )}
            </div>
          </div>
          
          <div className="grid gap-2">
            {displayedExamples.map((example: string, index: number) => {
              const isSelected = selectedExamples.has(index);
              const actualIndex = showAllExamples ? index : (index < 5 ? index : examples.indexOf(example));
              
              return (
                <ExampleCard
                  key={actualIndex}
                  example={example}
                  index={actualIndex + 1}
                  isSelected={isSelected}
                  onToggle={() => toggleExampleSelection(actualIndex)}
                />
              );
            })}
          </div>
          
          {!showAllExamples && examples.length > 5 && (
            <div className="text-center text-sm text-muted-foreground">
              Showing 5 of {examples.length} examples
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Individual Example Card Component
 * Compact display with click to expand, defensive design for long content
 */
const ExampleCard: React.FC<{
  example: string;
  index: number;
  isSelected: boolean;
  onToggle: () => void;
}> = ({ example, index, isSelected, onToggle }) => {
  const [expanded, setExpanded] = useState(false);
  const maxPreviewLength = 120;
  const isLong = example.length > maxPreviewLength;
  const displayText = expanded || !isLong ? example : `${example.slice(0, maxPreviewLength)}...`;

  return (
    <div
      className={`p-3 bg-card rounded cursor-pointer transition-colors ${
        isSelected 
          ? 'bg-primary/5' 
          : 'hover:bg-muted/20'
      }`}
      onClick={onToggle}
    >
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs font-mono text-muted-foreground">#{index}</span>
        <div className="flex items-center gap-1">
          {example.length > maxPreviewLength && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(!expanded);
              }}
            >
              {expanded ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            </Button>
          )}
          <span className="text-xs text-muted-foreground">
            {example.length} chars
          </span>
        </div>
      </div>
      <div className="text-sm font-mono text-foreground whitespace-pre-wrap break-words">
        {displayText}
      </div>
    </div>
  );
};

/**
 * BERTopic Analysis Section Component
 * Displays topics and visualization information
 */
const BERTopicSection: React.FC<{
  topics: Array<{
    id: number;
    name: string;
    count: number;
    representation: string;
    words: Array<{ word: string; weight: number }>;
  }>;
  bertopicAnalysis: any;
  visualizationNotes?: {
    topics_visualization?: string;
    heatmap_visualization?: string;
    available_files?: string;
  };
  attachedFiles?: string[];
}> = ({ topics, bertopicAnalysis, visualizationNotes, attachedFiles }) => {
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-muted-foreground">
        Automated topic discovery and clustering using BERTopic.
      </p>
      
      {/* BERTopic Configuration */}
      <div className="grid gap-2">
        {bertopicAnalysis.min_topic_size && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Min Topic Size:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">{bertopicAnalysis.min_topic_size}</div>
          </div>
        )}
        {bertopicAnalysis.num_topics_requested && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Requested Topics:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">{bertopicAnalysis.num_topics_requested}</div>
          </div>
        )}
        {bertopicAnalysis.top_n_words && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Top Words:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">{bertopicAnalysis.top_n_words}</div>
          </div>
        )}
        {bertopicAnalysis.min_ngram && bertopicAnalysis.max_ngram && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">N-gram Range:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">{bertopicAnalysis.min_ngram}-{bertopicAnalysis.max_ngram}</div>
          </div>
        )}
      </div>
      
      {topics.length > 0 ? (
        <div className="space-y-3">
          <h4 className="font-medium">Discovered Topics ({topics.length})</h4>
          <div className="grid gap-3">
            {topics.map((topic) => (
              <div key={topic.id} className="p-3 bg-card rounded">
                <div className="flex items-center justify-between mb-2">
                  <h5 className="font-medium">Topic {topic.id}</h5>
                  <span className="text-sm text-muted-foreground">{topic.count} items</span>
                </div>
                <p className="text-sm mb-2">{topic.name}</p>
                {topic.words && topic.words.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {topic.words.slice(0, 8).map((word, i) => (
                      <Badge key={i} variant="outline" className="text-xs">
                        {word.word} ({word.weight.toFixed(3)})
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-muted-foreground">
          No topics were discovered in the analysis.
        </div>
      )}
      
      {visualizationNotes && (
        <div className="p-3 bg-muted/30 rounded-md">
          <h5 className="font-medium mb-2">Visualization Status</h5>
          <div className="space-y-1 text-sm">
            {visualizationNotes.topics_visualization && (
              <div>• Topics: {visualizationNotes.topics_visualization}</div>
            )}
            {visualizationNotes.heatmap_visualization && (
              <div>• Heatmap: {visualizationNotes.heatmap_visualization}</div>
            )}
            {visualizationNotes.available_files && (
              <div>• Files: {visualizationNotes.available_files}</div>
            )}
          </div>
        </div>
      )}
      
      {attachedFiles && attachedFiles.length > 0 && (
        <div className="space-y-2">
          <h5 className="font-medium">Generated Files</h5>
          <div className="grid gap-1">
            {attachedFiles.map((file, i) => (
              <div key={i} className="text-sm text-muted-foreground">
                📎 {file}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Debug Information Section Component
 * Displays debugging information about the transformed text and processing
 */
const DebugInfoSection: React.FC<{
  debugInfo: {
    transformed_text_lines_count?: number;
    transformed_text_sample?: string[];
    unique_lines_count?: number;
    repetition_detected?: boolean;
    most_common_lines?: Array<{
      line: string;
      count: number;
    }>;
    error_reading_transformed_file?: string;
  };
}> = ({ debugInfo }) => {
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-muted-foreground">
        Debugging information about the LLM-transformed text and processing pipeline.
      </p>
      
      {debugInfo.error_reading_transformed_file && (
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
          <p className="text-sm text-destructive">
            Error reading transformed file: {debugInfo.error_reading_transformed_file}
          </p>
        </div>
      )}
      
      <div className="grid gap-3">
        {debugInfo.transformed_text_lines_count !== undefined && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Total Lines Generated:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">{debugInfo.transformed_text_lines_count.toLocaleString()}</div>
          </div>
        )}
        
        {debugInfo.unique_lines_count !== undefined && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Unique Lines:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">{debugInfo.unique_lines_count.toLocaleString()}</div>
          </div>
        )}
        
        {debugInfo.repetition_detected !== undefined && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Repetition Detected:</span>
            <div className="px-2 py-1 text-xs bg-card rounded">
              {debugInfo.repetition_detected ? "Yes" : "No"}
            </div>
          </div>
        )}
      </div>
      
      {debugInfo.transformed_text_sample && debugInfo.transformed_text_sample.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-medium text-sm">Sample of Transformed Text</h4>
          <div className="p-3 bg-muted/20 rounded-md border font-mono text-xs">
            {debugInfo.transformed_text_sample.map((line, index) => (
              <div key={index} className="py-1 border-b border-muted/30 last:border-b-0">
                <span className="text-muted-foreground mr-2">{index + 1}:</span>
                {line.trim()}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {debugInfo.most_common_lines && debugInfo.most_common_lines.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-medium text-sm">Most Repeated Lines</h4>
          <div className="space-y-2">
            {debugInfo.most_common_lines.map((item, index) => (
              <div key={index} className="p-2 bg-muted/20 rounded border">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-muted-foreground">
                    Repeated {item.count} times
                  </span>
                </div>
                <div className="text-sm font-mono">
                  {item.line}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Fine-tuning Section Component  
 * Displays representation model configuration and topic refinement
 */
const FineTuningSection: React.FC<{
  fineTuning: any;
  topics: Array<{
    id: number;
    name: string;
    count: number;
    representation: string;
    words: Array<{ word: string; weight: number }>;
  }>;
}> = ({ fineTuning, topics }) => {
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-muted-foreground">
        LLM-powered topic naming and representation refinement.
      </p>
      
      {fineTuning.use_representation_model && fineTuning.representation_model_provider && (
        <div className="space-y-2">
          <h4 className="font-medium">Representation Model</h4>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Provider:</span>
              <div className="px-2 py-1 text-xs bg-card rounded">{fineTuning.representation_model_provider}</div>
            </div>
            {fineTuning.representation_model_name && (
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Model:</span>
                <div className="px-2 py-1 text-xs bg-card rounded">{fineTuning.representation_model_name}</div>
              </div>
            )}
          </div>
        </div>
      )}
      
      {topics.length > 0 && fineTuning.use_representation_model && (
        <div className="space-y-3">
          <h4 className="font-medium">Refined Topic Names</h4>
          <div className="grid gap-2">
            {topics.map((topic) => (
              <div key={topic.id} className="flex items-center justify-between p-2 bg-card rounded">
                <div>
                  <span className="font-medium">Topic {topic.id}:</span>
                  <span className="ml-2">{topic.name}</span>
                </div>
                <span className="text-sm text-muted-foreground">{topic.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {!fineTuning.use_representation_model && (
        <div className="text-center py-8 text-muted-foreground">
          No representation model was used for topic refinement.
        </div>
      )}
    </div>
  );
};

// Set the blockClass property for the registry
(TopicAnalysis as any).blockClass = 'TopicAnalysis';

export default TopicAnalysis; 
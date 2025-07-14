"use client";

import React, { useState } from 'react';
import { ReportBlockProps } from './ReportBlock';
import ReportBlock from './ReportBlock';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown, ChevronUp, ChevronRight, Eye, EyeOff, MessagesSquare, Microscope, FileText, PocketKnife } from 'lucide-react';
import * as yaml from 'js-yaml';
import { PieChart, Pie, Cell, Tooltip, Label, ResponsiveContainer, Sector } from 'recharts';
import { PieSectorDataItem } from 'recharts/types/polar/Pie';
import { TopicAnalysisViewer } from '@/components/diagrams';
import { TemplateVariables } from '@/components/diagrams/topic-analysis-diagram';
import { 
  formatPreprocessor, 
  formatLLM, 
  formatBERTopic, 
  formatFineTuning 
} from '@/components/diagrams/text-formatting-utils';
import { IdentifierDisplay } from '../ui/identifier-display';

interface Identifier {
  id: string;
  name: string;
  url?: string;
}

interface TopicExample {
  id?: Identifier[] | string;
  text: string;
  [key: string]: any; // Allow other properties
}

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
    examples?: TopicExample[];
    llm_provider?: string;
    hit_rate_stats?: {
      total_processed: number;
      successful_extractions: number;
      failed_extractions: number;
      hit_rate_percentage: number;
    };
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
    topics_before?: Array<{
      topic_id: number;
      name: string;
      keywords: string[];
    }>;
    before_after_comparison?: Array<{
      topic_id: number;
      before_keywords: string[];
      before_name: string;
      after_name: string;
      enhanced: boolean;
    }>;
  };
  topics?: Array<{
    id: number;
    name: string;
    count: number;
    representation: string;
    keywords: string[];
    examples?: TopicExample[];
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
  const [selectedTopicIndex, setSelectedTopicIndex] = useState<number>(-1);
  const [completeTopicsData, setCompleteTopicsData] = useState<any>(null);
  const [loadingCompleteData, setLoadingCompleteData] = useState(false);

  // Function to fetch complete topics data from attached file
  const fetchCompleteTopicsData = async () => {
    if (loadingCompleteData || completeTopicsData) return;
    
    const topicsCompleteFile = props.attachedFiles?.find(file => 
      file.includes('topics_complete.json')
    );
    
    if (!topicsCompleteFile) {
      console.log('🔍 No topics_complete.json file found in attachedFiles:', props.attachedFiles);
      return;
    }
    
    try {
      setLoadingCompleteData(true);
      console.log('🔍 Fetching complete topics data from:', topicsCompleteFile);
      
      // Import AWS Amplify storage method
      const { downloadData } = await import('aws-amplify/storage');
      
      // Use appropriate bucket based on file path
      const storageOptions = {
        path: topicsCompleteFile,
        options: { bucket: 'reportBlockDetails' }
      };
      
      const downloadResult = await downloadData(storageOptions).result;
      const fileContent = await downloadResult.body.text();
      const completeData = JSON.parse(fileContent);
      
      console.log('🔍 Successfully loaded complete topics data:', {
        totalTopics: completeData.topics?.length || 0,
        hasAnalysisMetadata: !!completeData.analysis_metadata
      });
      
      setCompleteTopicsData(completeData);
    } catch (error) {
      console.error('❌ Failed to fetch complete topics data:', error);
    } finally {
      setLoadingCompleteData(false);
    }
  };
  
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
      // New format: parse YAML string
      data = yaml.load(props.output) as TopicAnalysisData;
    } else {
      // Legacy format: use object directly
      data = props.output as TopicAnalysisData;
    }
    
    // Debug the parsed data structure
    console.log('🔍 TopicAnalysis: Parsed data structure:', {
      dataType: typeof data,
      dataKeys: data ? Object.keys(data) : 'none',
      dataKeysCount: data ? Object.keys(data).length : 0,
      hasTopics: !!(data && data.topics),
      topicsType: data && data.topics ? typeof data.topics : 'none',
      topicsLength: data && data.topics && Array.isArray(data.topics) ? data.topics.length : 'not array'
    });
    
    // Safety check: if the parsed data looks like a massive array-like object, it's probably malformed
    if (data && Object.keys(data).length > 1000) {
      console.error('❌ TopicAnalysis: Parsed data has too many keys, likely malformed YAML:', Object.keys(data).length);
      return (
        <div className="p-4 text-center text-destructive">
          Error: Topic analysis data appears to be malformed (too many keys: {Object.keys(data).length}). Please regenerate the report.
        </div>
      );
    }
    
  } catch (error) {
    console.error('❌ TopicAnalysis: Failed to parse output data:', error);
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
  const summary = data.summary;
  
  // Debug logging for topics data
  console.log('🔍 TopicAnalysis: Topics data received:', {
    topicsCount: topics.length,
    topicsWithExamples: topics.filter(t => t.examples && t.examples.length > 0).length,
    sampleTopic: topics[0] ? {
      id: topics[0].id,
      name: topics[0].name,
      hasExamples: !!(topics[0].examples && topics[0].examples.length > 0),
      examplesCount: topics[0].examples?.length || 0
    } : 'No topics'
  });

  // Extract configuration summaries for the pipeline diagram
  const getDiagramVariables = (): TemplateVariables => {
    return {
      preprocessor: formatPreprocessor(
        preprocessing.method || 'Standard',
        preprocessing.sample_size
      ),
      LLM: formatLLM(
        llmExtraction.llm_provider || 'LLM',
        llmExtraction.llm_model,
        llmExtraction.prompt_used
      ),
      BERTopic: formatBERTopic({
        minTopicSize: bertopicAnalysis.min_topic_size,
        requestedTopics: bertopicAnalysis.num_topics_requested,
        minNgram: bertopicAnalysis.min_ngram,
        maxNgram: bertopicAnalysis.max_ngram,
        topNWords: bertopicAnalysis.top_n_words,
        discoveredTopics: topics.length
      }),
      finetune: formatFineTuning({
        useRepresentationModel: fineTuning.use_representation_model || false,
        provider: fineTuning.representation_model_provider,
        model: fineTuning.representation_model_name
      })
    };
  };



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
        <TopicAnalysisResults 
          topics={topics} 
          summary={summary} 
          bertopicAnalysis={bertopicAnalysis}
          completeTopicsData={completeTopicsData}
          loadingCompleteData={loadingCompleteData}
          fetchCompleteTopicsData={fetchCompleteTopicsData}
        />

        {/* Pipeline Setup */}
        <div className="w-full">
          <div className="text-lg font-medium mb-4">
            <div className="flex items-center gap-2">
              <PocketKnife className="h-5 w-5" />
              Pipeline Setup
            </div>
          </div>
          <Card>
            <CardContent className="p-0">
              <TopicAnalysisViewer 
                variables={getDiagramVariables()}
                className="rounded-lg"
                viewModeEnabled={true}
                height={600}
              />
            </CardContent>
          </Card>
        </div>

        {/* Analysis Details Section */}
        <div className="w-full">
          <div className="text-lg font-medium mb-6">
            <div className="flex items-center gap-2">
              <Microscope className="h-5 w-5" />
              Analysis Details
            </div>
          </div>
          <div className="space-y-6 [&>*:last-child]:border-b-0">
            {/* Pre-processing Section */}
            <Accordion type="multiple" defaultValue={[]} className="w-full">
              <AccordionItem value="preprocessing">
                <AccordionTrigger className="text-base font-medium">
                  Pre-processing
                </AccordionTrigger>
                <AccordionContent>
                  <PreprocessingSection preprocessing={preprocessing} />
                </AccordionContent>
              </AccordionItem>
            </Accordion>

            {/* LLM Extraction Section */}
            <Accordion type="multiple" defaultValue={[]} className="w-full">
              <AccordionItem value="llm-extraction">
                <AccordionTrigger className="text-base font-medium">
                  LLM Extraction
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
            </Accordion>

            {/* BERTopic Analysis Section */}
            <Accordion type="multiple" defaultValue={[]} className="w-full">
              <AccordionItem value="bertopic">
                <AccordionTrigger className="text-base font-medium">
                  BERTopic Analysis
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
            </Accordion>

            {/* Fine-tuning Section */}
            <Accordion type="multiple" defaultValue={[]} className="w-full">
              <AccordionItem value="fine-tuning">
                <AccordionTrigger className="text-base font-medium">
                  Fine-tuning
                </AccordionTrigger>
                <AccordionContent>
                  <FineTuningSection 
                    fineTuning={fineTuning}
                    topics={topics}
                    bertopicAnalysis={bertopicAnalysis}
                  />
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>
        </div>
      </div>
    </ReportBlock>
  );
};

/**
 * Helper function to clean topic names by removing prefixes like "0_"
 */
const cleanTopicName = (name: string): string => {
  // Remove prefixes like "0_", "1_", etc., replace underscores, and capitalize
  const cleaned = name.replace(/^\d+_/, '');
  return cleaned
    .replace(/_/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase());
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
    keywords: string[];
    examples?: TopicExample[];
  }>;
  summary?: string;
  bertopicAnalysis?: any;
  completeTopicsData?: any;
  loadingCompleteData?: boolean;
  fetchCompleteTopicsData?: () => void;
}> = ({ topics, summary, bertopicAnalysis, completeTopicsData, loadingCompleteData, fetchCompleteTopicsData }) => {
  const [selectedTopicIndex, setSelectedTopicIndex] = useState<number>(-1);

  if (topics.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <MessagesSquare className="h-5 w-5" />
          <h3 className="text-lg font-medium">Topic Analysis Results</h3>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>No Topics Discovered</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {summary || "The analysis completed, but no distinct topics were found in the data. You could try adjusting the analysis parameters, like 'min_topic_size', or increasing the sample size."}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <MessagesSquare className="h-5 w-5" />
        <h3 className="text-lg font-medium">Topic Analysis Results</h3>
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-5 gap-8 items-start">
        <div className="sticky top-4 sm:col-span-2">
          <TopicDistributionChart 
            topics={topics} 
            selectedIndex={selectedTopicIndex}
            onTopicSelect={setSelectedTopicIndex}
          />
        </div>
        
        <div className="sm:col-span-3">
          <Accordion 
            type="single" 
            collapsible 
            className="w-full" 
            value={selectedTopicIndex >= 0 ? `item-${selectedTopicIndex}` : ""}
            onValueChange={(value) => {
              if (value && value !== "") {
                const index = parseInt(value.replace('item-', ''));
                setSelectedTopicIndex(index);
              } else {
                setSelectedTopicIndex(-1);
              }
            }}
          >
            {topics.map((topic, index) => {
              const isSelected = selectedTopicIndex === index;
              
              // Get examples from complete data if available
              const getTopicExamples = () => {
                if (topic.examples && topic.examples.length > 0) {
                  return topic.examples;
                }
                
                if (completeTopicsData?.topics) {
                  const completeTopic = completeTopicsData.topics.find((t: any) => t.id === topic.id);
                  return completeTopic?.examples || [];
                }
                
                return [];
              };
              
              const topicExamples = getTopicExamples();
              
              return (
                <AccordionItem key={topic.id} value={`item-${index}`} className="mb-4">
                  <AccordionTrigger 
                    className={`py-2 px-3 rounded-lg transition-colors ${
                      isSelected ? 'bg-primary text-primary-foreground' : 'hover:bg-muted/50'
                    }`}
                    onClick={() => {
                      // Load complete data when a topic is expanded
                      if ((isSelected || selectedTopicIndex !== index) && fetchCompleteTopicsData) {
                        fetchCompleteTopicsData();
                      }
                    }}
                  >
                    <div className="flex items-center justify-between w-full pr-4">
                      <span className="font-medium text-left">{cleanTopicName(topic.name)}</span>
                      <Badge variant="secondary" className="border-none bg-card font-normal">{topic.count} items</Badge>
                    </div>
                  </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-3 p-1">
                    {topic.keywords && topic.keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {topic.keywords
                          .filter(keyword => {
                            // Ensure keyword is a non-empty string
                            if (!keyword || typeof keyword !== 'string' || keyword.trim() === '') {
                              return false;
                            }
                            // Also filter out the main topic name itself
                            const normalizedKeyword = keyword.toLowerCase().replace(/_/g, ' ').trim();
                            const normalizedTopicName = cleanTopicName(topic.name).toLowerCase().trim();
                            return normalizedKeyword !== normalizedTopicName;
                          })
                          .slice(0, bertopicAnalysis.top_n_words || 8)
                          .map((keyword, i) => (
                            <Badge key={i} variant="secondary" className="text-xs">
                              {keyword}
                            </Badge>
                          ))}
                      </div>
                    )}
                    
                    {loadingCompleteData && (
                      <div className="text-xs text-muted-foreground italic">
                        Loading examples...
                      </div>
                    )}
                    
                    {!loadingCompleteData && topicExamples.length > 0 && (
                      <TopicExamplesSection examples={topicExamples} />
                    )}
                    
                    {!loadingCompleteData && topicExamples.length === 0 && (
                      <div className="text-xs text-muted-foreground italic">
                        No examples available for this topic
                      </div>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
              );
            })}
          </Accordion>
        </div>
      </div>
    </div>
  );
};

/**
 * Topic Examples Section Component
 * Shows representative example texts for a topic with collapsible display
 */
const TopicExamplesSection: React.FC<{
  examples: TopicExample[];
}> = ({ examples }) => {
  if (!examples || examples.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mt-2">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <h5 className="text-sm font-medium">Examples</h5>
      </div>
      <div className="space-y-2 pl-6">
        {examples.map((example, index) => {
          // Debug: Log the structure of example objects to see what metadata is available
          if (index === 0 && typeof example === 'object') {
            console.log('🔍 TopicAnalysis: Example object structure:', {
              keys: Object.keys(example),
              example: example,
              hasIds: 'ids' in example,
              hasId: 'id' in example,
              hasText: 'text' in example
            });
          }
          
          // Extract text and metadata from object or use as string
          let displayText: string;
          let metadata: any = null;
          
          if (typeof example === 'string') {
            displayText = example;
          } else if (typeof example === 'object' && example !== null) {
            // If it's an object with a 'text' property, extract that
            const exampleObj = example as any;
            if ('text' in exampleObj && typeof exampleObj.text === 'string') {
              displayText = exampleObj.text;
              metadata = exampleObj; // Store the full object for metadata access
            } else {
              // Fallback to stringifying the whole object
              displayText = JSON.stringify(example);
            }
          } else {
            displayText = String(example);
          }
          
          return (
            <div key={index} className="p-2 bg-muted/20 rounded-md border-l-2 border-muted-foreground/40">
              {/* Display identifier/metadata if available */}
              {(metadata?.id || metadata?.ids) && (
                <div className="mb-2">
                  {(() => {
                    let identifierArray: Identifier[] = [];
                    
                    // Check both 'id' and 'ids' fields for backward compatibility
                    const idField = metadata?.id || metadata?.ids;
                    
                    // Handle different formats of the id field
                    if (Array.isArray(idField)) {
                      identifierArray = idField;
                    } else if (typeof idField === 'string') {
                      try {
                        const parsed = JSON.parse(idField);
                        if (Array.isArray(parsed)) {
                          identifierArray = parsed;
                        }
                      } catch (e) {
                        // If parsing fails, treat as a simple string ID
                        identifierArray = [{ id: idField, name: 'ID' }];
                      }
                    }
                    
                    // Only render if we have valid identifiers
                    if (identifierArray.length > 0) {
                      return (
                        <IdentifierDisplay 
                          identifiers={
                            identifierArray.map(identifier => ({
                                name: identifier.name || 'ID',
                                value: identifier.id,
                                url: identifier.url
                            }))
                          }
                          iconSize="sm"
                          textSize="xs"
                        />
                      );
                    }
                    return null;
                  })()}
                </div>
              )}
              <p className="text-sm text-foreground whitespace-pre-wrap break-words">
                {displayText}
              </p>
            </div>
          );
        })}
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
 * LLM Extraction Hit Rate Chart Component
 * Shows the success rate of LLM extraction as a pie chart
 */
const LLMExtractionHitRateChart: React.FC<{
  hitRateStats: {
    total_processed: number;
    successful_extractions: number;
    failed_extractions: number;
    hit_rate_percentage: number;
  };
}> = ({ hitRateStats }) => {
  // Get the computed CSS custom property values for true/false colors
  const trueColor = React.useMemo(() => {
    if (typeof window !== 'undefined') {
      const style = getComputedStyle(document.documentElement);
      return style.getPropertyValue('--true').trim();
    }
    return 'hsl(142 76% 36%)'; // fallback
  }, []);

  const falseColor = React.useMemo(() => {
    if (typeof window !== 'undefined') {
      const style = getComputedStyle(document.documentElement);
      return style.getPropertyValue('--false').trim();
    }
    return 'hsl(358 75% 59%)'; // fallback
  }, []);

  const chartData = [
    {
      name: "Successful",
      value: hitRateStats.successful_extractions,
      percentage: hitRateStats.hit_rate_percentage,
    },
    {
      name: "Failed", 
      value: hitRateStats.failed_extractions,
      percentage: 100 - hitRateStats.hit_rate_percentage,
    }
  ];

  return (
    <div className="space-y-3">
      <h4 className="font-medium">Extraction Hit Rate</h4>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
        <div className="w-full aspect-square max-w-[200px] mx-auto" style={{ pointerEvents: 'none' }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                innerRadius="50%"
                outerRadius="80%"
                strokeWidth={2}
                stroke="hsl(var(--background))"
                paddingAngle={2}
                onClick={() => {}}
                onMouseEnter={() => {}}
                onMouseLeave={() => {}}
              >
                <Cell fill={trueColor} style={{ outline: 'none', cursor: 'default' }} />
                <Cell fill={falseColor} style={{ outline: 'none', cursor: 'default' }} />
                <Label
                  content={({ viewBox }) => {
                    if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                      return (
                        <text
                          x={viewBox.cx}
                          y={viewBox.cy}
                          textAnchor="middle"
                          dominantBaseline="middle"
                        >
                          <tspan
                            x={viewBox.cx}
                            y={viewBox.cy}
                            className="fill-foreground text-2xl font-bold"
                          >
                            {hitRateStats.hit_rate_percentage}%
                          </tspan>
                        </text>
                      );
                    }
                    return null;
                  }}
                  position="center"
                />
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-true"></div>
              <span className="text-sm font-medium">Successful</span>
            </div>
            <span className="text-sm text-muted-foreground">
              {hitRateStats.successful_extractions} items
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-false"></div>
              <span className="text-sm font-medium">Failed</span>
            </div>
            <span className="text-sm text-muted-foreground">
              {hitRateStats.failed_extractions} items
            </span>
          </div>
          <div className="pt-2 border-t">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Total Processed</span>
              <span className="text-sm text-muted-foreground">
                {hitRateStats.total_processed} items
              </span>
            </div>
          </div>
        </div>
      </div>
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
  const displayedExamples = showAllExamples ? examples : examples.slice(0, 20);
  
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

      {/* Hit Rate Section */}
      {llmExtraction.hit_rate_stats && (
        <>
          {llmExtraction.hit_rate_stats.total_processed > 0 ? (
            <LLMExtractionHitRateChart hitRateStats={llmExtraction.hit_rate_stats} />
          ) : (
            <div className="space-y-3">
              <h4 className="font-medium">Extraction Hit Rate</h4>
              <div className="p-3 bg-muted/20 rounded-md border-l-2 border-primary/20">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 rounded-full bg-primary"></div>
                  <span className="text-sm font-medium">Using Cached Results</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  This analysis used previously processed data for faster results. 
                  Hit rate statistics are only available when processing fresh data.
                </p>
              </div>
            </div>
          )}
        </>
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
              {examples.length > 20 && (
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
            {displayedExamples.map((example: TopicExample, index: number) => {
              const isSelected = selectedExamples.has(index);
              const actualIndex = showAllExamples ? index : (index < 20 ? index : examples.indexOf(example));
              
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
          
          {!showAllExamples && examples.length > 20 && (
            <div className="text-center text-sm text-muted-foreground">
              Showing 20 of {examples.length} examples
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
  example: TopicExample;
  index: number;
  isSelected: boolean;
  onToggle: () => void;
}> = ({ example, index, isSelected, onToggle }) => {
  const [expanded, setExpanded] = useState(false);
  const maxPreviewLength = 120;
  
  // Extract text and metadata from object or use as string
  let safeExample: string;
  let metadata: any = null;
  
  if (typeof example === 'string') {
    safeExample = example;
  } else if (typeof example === 'object' && example !== null) {
    // If it's an object with a 'text' property, extract that
    const exampleObj = example as any;
    if ('text' in exampleObj && typeof exampleObj.text === 'string') {
      safeExample = exampleObj.text;
      metadata = exampleObj; // Store the full object for metadata access
    } else {
      // Fallback to stringifying the whole object
      safeExample = JSON.stringify(example);
    }
  } else {
    safeExample = String(example);
  }
  
  const isLong = safeExample.length > maxPreviewLength;
  const displayText = expanded || !isLong ? safeExample : `${safeExample.slice(0, maxPreviewLength)}...`;

  // Safely parse the ID field if it's a string
  let parsedId: Identifier[] | null = null;
  if (metadata?.id) {
    if (Array.isArray(metadata.id)) {
      parsedId = metadata.id;
    } else if (typeof metadata.id === 'string') {
      try {
        const parsed = JSON.parse(metadata.id);
        if (Array.isArray(parsed)) {
          parsedId = parsed;
        }
      } catch (e) {
        // Not a valid JSON string, so we can't parse it.
        // It will be handled as a plain string below.
      }
    }
  }

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
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-mono text-muted-foreground">#{index}</span>
          {/* Display identifier if available */}
          {parsedId ? (
            parsedId.map((identifier: Identifier) => (
              identifier.url ? (
                <a 
                  href={identifier.url} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  key={identifier.id} 
                  onClick={(e) => e.stopPropagation()}
                  className="text-xs font-mono bg-muted px-1 py-0.5 rounded text-muted-foreground hover:bg-primary/20 hover:text-primary-foreground"
                >
                  {identifier.name}: {identifier.id}
                </a>
              ) : (
                <span key={identifier.id} className="text-xs font-mono bg-muted px-1 py-0.5 rounded text-muted-foreground">
                  {identifier.name}: {identifier.id}
                </span>
              )
            ))
          ) : metadata?.id ? (
            <span className="text-xs font-mono bg-muted px-1 py-0.5 rounded text-muted-foreground">
              ID: {String(metadata.id)}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-1">
          {safeExample.length > maxPreviewLength && (
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
            {safeExample.length} chars
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
    keywords: string[];
    examples?: TopicExample[];
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
                {topic.keywords && topic.keywords.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {topic.keywords.slice(0, bertopicAnalysis?.top_n_words || 8).map((keyword, i) => (
                      <Badge key={i} variant="outline" className="text-xs">
                        {keyword}
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
    keywords: string[];
    examples?: TopicExample[];
  }>;
  bertopicAnalysis?: any;
}> = ({ fineTuning, topics, bertopicAnalysis }) => {

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
      
      {fineTuning.before_after_comparison && fineTuning.before_after_comparison.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium">Before & After Fine-tuning Comparison</h4>
          <p className="text-sm text-muted-foreground">
            See how the LLM transformed keyword-based topic names into human-readable labels.
          </p>
          <div className="grid gap-3">
            {fineTuning.before_after_comparison.map((comparison: any) => {
              const afterTopic = topics.find(t => t.id === comparison.topic_id);
              if (!afterTopic) return null;
              
              return (
                <div key={comparison.topic_id} className="border rounded-lg p-4 bg-card">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Topic {comparison.topic_id}</span>
                      <Badge variant="outline" className="text-xs">
                        {afterTopic.count} items
                      </Badge>
                    </div>
                  </div>
                  
                  <div className="grid md:grid-cols-2 gap-4">
                    {/* Before (Original Keywords) */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-muted-foreground">Before</span>
                      </div>
                      <div className="space-y-2">
                        <h5 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Original Keywords</h5>
                        <div className="p-3 bg-muted/30 rounded border-l-2 border-primary/20">
                          <div className="flex flex-wrap gap-1">
                            {comparison.before_keywords.slice(0, bertopicAnalysis?.top_n_words || 8).map((keyword: string, i: number) => (
                              <Badge key={i} variant="outline" className="text-xs">
                                {keyword}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    {/* After (LLM Refined) */}
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-muted-foreground">After</span>
                      </div>
                      <div className="space-y-2">
                        <h5 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">LLM Refined</h5>
                        <div className="p-3 bg-primary/5 rounded border-l-2 border-primary/20">
                          <p className="text-sm font-medium">
                            {comparison.after_name}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Fallback: Show only refined names if no before/after comparison data */}
      {(!fineTuning.before_after_comparison || fineTuning.before_after_comparison.length === 0) && topics.length > 0 && fineTuning.use_representation_model && (
        <div className="space-y-3">
          <h4 className="font-medium">Refined Topic Names</h4>
          <div className="grid gap-2">
            {topics.map((topic) => (
              <div key={topic.id} className="flex items-center justify-between p-2 bg-card rounded">
                <div>
                  <span className="font-medium">Topic {topic.id}</span>
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

/**
 * Topic Distribution Chart Component
 * Displays a pie chart for topic distribution
 */
const TopicDistributionChart: React.FC<{
  topics: Array<{
    id: number;
    name: string;
    count: number;
  }>;
  selectedIndex: number;
  onTopicSelect: (index: number) => void;
}> = ({ topics, selectedIndex, onTopicSelect }) => {
  const chartData = topics.map(topic => ({
    name: cleanTopicName(topic.name),
    value: topic.count,
  }));

  const handlePieClick = (data: any, index: number) => {
    // Toggle selection - if clicking the same segment, deselect it
    if (selectedIndex === index) {
      onTopicSelect(-1);
    } else {
      onTopicSelect(index);
    }
  };

  return (
    <div className="w-full mx-auto aspect-square">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={chartData}
            dataKey="value"
            nameKey="name"
            innerRadius="60%"
            outerRadius="80%"
            strokeWidth={2}
            stroke="hsl(var(--background))"
            paddingAngle={2}
            activeIndex={selectedIndex >= 0 ? selectedIndex : undefined}
            activeShape={({
              outerRadius = 0,
              ...props
            }: PieSectorDataItem) => (
              <Sector {...props} outerRadius={outerRadius + 20} />
            )}
            onClick={handlePieClick}
          >
            {chartData.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={`var(--chart-${(index % 7) + 1})`}
                style={{ cursor: 'pointer', outline: 'none' }}
              />
            ))}
            <Label
              content={({ viewBox }) => {
                if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                  return (
                    <text
                      x={viewBox.cx}
                      y={viewBox.cy}
                      textAnchor="middle"
                      dominantBaseline="middle"
                    >
                      <tspan
                        x={viewBox.cx}
                        y={viewBox.cy}
                        className="fill-foreground text-3xl font-bold"
                      >
                        {topics.length.toLocaleString()}
                      </tspan>
                      <tspan
                        x={viewBox.cx}
                        y={(viewBox.cy || 0) + 24}
                        className="fill-muted-foreground"
                      >
                        Topics
                      </tspan>
                    </text>
                  );
                }
                return null;
              }}
              position="center"
            />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

// Set the blockClass property for the registry
(TopicAnalysis as any).blockClass = 'TopicAnalysis';

export default TopicAnalysis; 
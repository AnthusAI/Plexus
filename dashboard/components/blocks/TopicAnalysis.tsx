"use client";

import React, { useState } from 'react';
import { ReportBlockProps } from './ReportBlock';
import ReportBlock from './ReportBlock';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown, ChevronUp, ChevronRight, Eye, EyeOff, MessagesSquare, Microscope, FileText } from 'lucide-react';
import * as yaml from 'js-yaml';
import { PieChart, Pie, Cell, Tooltip, Label, ResponsiveContainer, Sector } from 'recharts';
import { PieSectorDataItem } from 'recharts/types/polar/Pie';

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
    topics_before?: Array<{
      id: number;
      name: string;
      count: number;
      representation: string;
      words: Array<{ word: string; weight: number }>;
    }>;
  };
  topics?: Array<{
    id: number;
    name: string;
    count: number;
    representation: string;
    words: Array<{ word: string; weight: number }>;
    examples?: string[];
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
    words: Array<{ word: string; weight: number }>;
    examples?: string[];
  }>;
}> = ({ topics }) => {
  const [selectedTopicIndex, setSelectedTopicIndex] = useState<number>(-1);

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
            value={selectedTopicIndex >= 0 ? `item-${selectedTopicIndex}` : undefined}
            onValueChange={(value) => {
              if (value) {
                const index = parseInt(value.replace('item-', ''));
                setSelectedTopicIndex(index);
              } else {
                setSelectedTopicIndex(-1);
              }
            }}
          >
            {topics.map((topic, index) => (
              <AccordionItem key={topic.id} value={`item-${index}`} className="mb-4">
                <AccordionTrigger className="py-2">
                  <div className="flex items-center justify-between w-full pr-4">
                    <span className="font-medium text-left">{cleanTopicName(topic.name)}</span>
                    <Badge variant="secondary" className="border-none bg-card font-normal">{topic.count} items</Badge>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-3 p-1">
                    {topic.words && topic.words.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {topic.words
                          .filter(word => {
                            // Filter out empty or blank words
                            if (!word.word || word.word.trim() === '') {
                              return false;
                            }
                            // More robustly filter out the topic name from keywords
                            const normalizedWord = word.word.toLowerCase().replace(/_/g, ' ').trim();
                            const normalizedTopicName = cleanTopicName(topic.name).toLowerCase().trim();
                            return normalizedWord !== normalizedTopicName;
                          })
                          .slice(0, 6)
                          .map((word, i) => (
                            <Badge key={i} variant="secondary" className="text-xs">
                              {word.word}
                            </Badge>
                          ))}
                      </div>
                    )}
                    {topic.examples && topic.examples.length > 0 && (
                      <TopicExamplesSection examples={topic.examples} />
                    )}
                    {(!topic.examples || topic.examples.length === 0) && (
                      <div className="text-xs text-muted-foreground italic">
                        No examples available for this topic
                      </div>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
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
  examples: string[];
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
        {examples.map((example, index) => (
          <div key={index} className="p-2 bg-muted/20 rounded-md border-l-2 border-muted-foreground/40">
            <p className="text-sm text-foreground whitespace-pre-wrap break-words">
              {example}
            </p>
          </div>
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
            {displayedExamples.map((example: string, index: number) => {
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
    examples?: string[];
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
    examples?: string[];
  }>;
}> = ({ fineTuning, topics }) => {
  const topicsBefore = fineTuning.topics_before || [];
  const hasBeforeAfterData = topicsBefore.length > 0 && topics.length > 0;

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
      
      {hasBeforeAfterData && fineTuning.use_representation_model && (
        <div className="space-y-3">
          <h4 className="font-medium">Before & After Fine-tuning Comparison</h4>
          <p className="text-sm text-muted-foreground">
            See how the LLM transformed keyword-based topic names into human-readable labels.
          </p>
          <div className="grid gap-3">
            {topics.map((afterTopic) => {
              // Find the corresponding "before" topic by ID
              const beforeTopic = topicsBefore.find((bt: any) => bt.id === afterTopic.id);
              
              if (!beforeTopic) return null;
              
              return (
                <div key={afterTopic.id} className="border rounded-lg p-4 bg-card">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Topic {afterTopic.id + 1}</span>
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
                            {beforeTopic.words.slice(0, 6).map((word: any, i: number) => (
                              <Badge key={i} variant="outline" className="text-xs">
                                {word.word}
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
                          <p className="text-sm font-medium mb-2">
                            {cleanTopicName(afterTopic.name)}
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {afterTopic.words
                              .filter((word: any) => !cleanTopicName(afterTopic.name).toLowerCase().includes(word.word.toLowerCase()))
                              .slice(0, 6)
                              .map((word: any, i: number) => (
                                <Badge key={i} variant="outline" className="text-xs">
                                  {word.word}
                                </Badge>
                              ))}
                          </div>
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

      {/* Fallback: Show only refined names if no before data */}
      {!hasBeforeAfterData && topics.length > 0 && fineTuning.use_representation_model && (
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
              <Sector {...props} outerRadius={outerRadius + 10} />
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
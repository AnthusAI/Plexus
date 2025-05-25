import React, { useState } from 'react';
import { ReportBlockProps } from './ReportBlock';
import ReportBlock from './ReportBlock';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown, ChevronRight, Eye, EyeOff, TrendingUp } from 'lucide-react';

interface TopicAnalysisData {
  summary?: string;
  transformed_text_file?: string;
  skipped_files?: string[];
  preprocessing?: {
    llm_model?: string;
    method?: string;
    prompt_used?: string;
    examples?: string[];
    llm_provider?: string;
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

  const data = props.output as TopicAnalysisData;
  const preprocessing = data.preprocessing || {};
  const topics = data.topics || [];
  const errors = data.errors || [];

  console.log('✅ TopicAnalysis: Rendering with structured data:', data);

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
              <Badge variant="outline" className="ml-2">
                {preprocessing.method || 'programmatic'}
              </Badge>
            </AccordionTrigger>
          <AccordionContent>
            <div className="space-y-3 pt-2">
              <p className="text-sm text-muted-foreground">
                Programmatic data preparation and filtering step.
              </p>
              {preprocessing.method && (
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Method:</span>
                  <Badge variant="secondary">{preprocessing.method}</Badge>
                </div>
              )}
              {data.transformed_text_file && (
                <div className="text-xs text-muted-foreground">
                  Output: {data.transformed_text_file.split('/').pop()}
                </div>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* LLM Extraction Section */}
        <AccordionItem value="llm-extraction">
          <AccordionTrigger className="text-base font-medium">
            LLM Extraction
            {preprocessing.examples && (
              <Badge variant="default" className="ml-2">
                {preprocessing.examples.length} examples
              </Badge>
            )}
          </AccordionTrigger>
          <AccordionContent>
            <LLMExtractionSection 
              preprocessing={preprocessing}
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
              <Badge variant="default" className="ml-2">
                {topics.length} topics
              </Badge>
            )}
          </AccordionTrigger>
          <AccordionContent>
            <BERTopicSection 
              topics={topics}
              visualizationNotes={data.visualization_notes}
              attachedFiles={props.attachedFiles || undefined}
            />
          </AccordionContent>
        </AccordionItem>

        {/* Fine-tuning Section */}
        <AccordionItem value="fine-tuning">
          <AccordionTrigger className="text-base font-medium">
            Fine-tuning
            {preprocessing.representation_model_provider && (
              <Badge variant="outline" className="ml-2">
                {preprocessing.representation_model_name || preprocessing.representation_model_provider}
              </Badge>
            )}
          </AccordionTrigger>
          <AccordionContent>
            <FineTuningSection 
              preprocessing={preprocessing}
              topics={topics}
            />
          </AccordionContent>
          </AccordionItem>
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
          <TrendingUp className="h-5 w-5" />
          <h3 className="text-lg font-medium">Topic Analysis Results</h3>
        </div>
        <div className="text-center py-12 text-muted-foreground bg-muted/20 rounded-lg border-2 border-dashed">
          <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg mb-2">No Topics Discovered</p>
          <p className="text-sm">The analysis did not identify distinct topics in the data.</p>
          <p className="text-sm mt-2">Consider adjusting the configuration parameters or increasing the sample size.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          <h3 className="text-lg font-medium">Topic Analysis Results</h3>
        </div>
        <Badge variant="default">{topics.length} topics discovered</Badge>
      </div>
      
      <div className="grid gap-4 md:grid-cols-2">
        {topics.map((topic) => (
          <Card key={topic.id} className="border-l-4 border-l-primary">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Topic {topic.id}</CardTitle>
                <Badge variant="secondary">{topic.count} items</Badge>
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
 * LLM Extraction Section Component
 * Displays the prompt and extracted examples with collapsible/expandable sections
 */
const LLMExtractionSection: React.FC<{
  preprocessing: any;
  promptExpanded: boolean;
  setPromptExpanded: (expanded: boolean) => void;
  examplesExpanded: boolean;
  setExamplesExpanded: (expanded: boolean) => void;
}> = ({ preprocessing, promptExpanded, setPromptExpanded, examplesExpanded, setExamplesExpanded }) => {
  const [selectedExamples, setSelectedExamples] = useState<Set<number>>(new Set());
  const [showAllExamples, setShowAllExamples] = useState(false);
  
  const examples = preprocessing.examples || [];
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
      <div className="flex flex-wrap gap-2">
        {preprocessing.llm_provider && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Provider:</span>
            <Badge variant="secondary">{preprocessing.llm_provider}</Badge>
          </div>
        )}
        {preprocessing.llm_model && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Model:</span>
            <Badge variant="outline">{preprocessing.llm_model}</Badge>
          </div>
        )}
      </div>

      {/* Collapsible Prompt Section */}
      {preprocessing.prompt_used && (
        <div className="border rounded-md">
          <Collapsible open={promptExpanded} onOpenChange={setPromptExpanded}>
            <CollapsibleTrigger asChild>
              <Button 
                variant="ghost" 
                className="w-full justify-between p-4 h-auto font-normal"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium">Extraction Prompt</span>
                  <Badge variant="secondary">
                    {preprocessing.prompt_used.length} chars
                  </Badge>
                </div>
                {promptExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="px-4 pb-4">
                <pre className="text-xs bg-muted p-3 rounded border overflow-x-auto whitespace-pre-wrap">
                  {preprocessing.prompt_used}
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
      className={`p-3 border rounded-md cursor-pointer transition-colors ${
        isSelected 
          ? 'border-primary bg-primary/5' 
          : 'border-border hover:border-muted-foreground/20'
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
  visualizationNotes?: {
    topics_visualization?: string;
    heatmap_visualization?: string;
    available_files?: string;
  };
  attachedFiles?: string[];
}> = ({ topics, visualizationNotes, attachedFiles }) => {
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-muted-foreground">
        Automated topic discovery and clustering using BERTopic.
      </p>
      
      {topics.length > 0 ? (
        <div className="space-y-3">
          <h4 className="font-medium">Discovered Topics ({topics.length})</h4>
          <div className="grid gap-3">
            {topics.map((topic) => (
              <div key={topic.id} className="p-3 border rounded-md">
                <div className="flex items-center justify-between mb-2">
                  <h5 className="font-medium">Topic {topic.id}</h5>
                  <Badge variant="secondary">{topic.count} items</Badge>
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
 * Fine-tuning Section Component  
 * Displays representation model configuration and topic refinement
 */
const FineTuningSection: React.FC<{
  preprocessing: any;
  topics: Array<{
    id: number;
    name: string;
    count: number;
    representation: string;
    words: Array<{ word: string; weight: number }>;
  }>;
}> = ({ preprocessing, topics }) => {
  return (
    <div className="space-y-4 pt-2">
      <p className="text-sm text-muted-foreground">
        LLM-powered topic naming and representation refinement.
      </p>
      
      {preprocessing.representation_model_provider && (
        <div className="space-y-2">
          <h4 className="font-medium">Representation Model</h4>
          <div className="flex gap-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Provider:</span>
              <Badge variant="secondary">{preprocessing.representation_model_provider}</Badge>
            </div>
            {preprocessing.representation_model_name && (
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Model:</span>
                <Badge variant="outline">{preprocessing.representation_model_name}</Badge>
              </div>
            )}
          </div>
        </div>
      )}
      
      {topics.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium">Refined Topic Names</h4>
          <div className="grid gap-2">
            {topics.map((topic) => (
              <div key={topic.id} className="flex items-center justify-between p-2 border rounded">
                <div>
                  <span className="font-medium">Topic {topic.id}:</span>
                  <span className="ml-2">{topic.name}</span>
                </div>
                <Badge variant="outline">{topic.count}</Badge>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {!preprocessing.representation_model_provider && (
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
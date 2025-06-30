import { Button as DocButton } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import Link from "next/link"
import { MessageCircle, Code, FileText, TrendingUp, Brain, PieChart } from 'lucide-react'
import TopicAnalysis from '@/components/blocks/TopicAnalysis'

// Example output data that matches the actual structure from the TopicAnalysis block
const exampleOutput = `# Topic Analysis Report Output
#
# This is the structured output from a topic analysis process that:
# 1. Transforms text data using various methods (chunking, LLM extraction, itemization)
# 2. Applies BERTopic clustering to identify topics in the text
# 3. Generates topic visualizations and keyword lists
# 4. Provides representative examples for each discovered topic

summary: "Topic analysis block execution."
transformed_text_file: "/tmp/plexus_transform_abcd1234/transformed_text.txt"
skipped_files: []
errors: []
preprocessing:
  method: "chunk"
  input_file: "/workspace/data/transcripts.parquet"
  content_column: "text"
  sample_size: null
  customer_only: false
  data:
    source_identifier: "customer-calls"
    dataset_identifier: null
    fresh_data: false
    metadata:
      source_type: "parquet"
      name: "Customer Call Transcripts"
llm_extraction:
  method: "chunk"
  examples:
    - "Customer called to inquire about their billing statement and wanted clarification on charges."
    - "Representative helped resolve a technical issue with the customer's account access."
    - "Customer requested to cancel their service and was offered retention incentives."
  hit_rate_stats:
    total_processed: 245
    successful_extractions: 238
    failed_extractions: 7
    hit_rate_percentage: 97.14
bertopic_analysis:
  num_topics_requested: null
  min_topic_size: 10
  top_n_words: 10
  min_ngram: 1
  max_ngram: 2
  skip_analysis: false
fine_tuning:
  use_representation_model: false
  representation_model_provider: "openai"
  representation_model_name: "gpt-4o-mini"
topics:
  - id: 0
    name: "billing_inquiry"
    count: 45
    representation: "billing account charges statement payment"
    words:
      - word: "billing"
        weight: 0.156
      - word: "account"
        weight: 0.134
      - word: "charges"
        weight: 0.128
      - word: "statement"
        weight: 0.115
      - word: "payment"
        weight: 0.098
      - word: "invoice"
        weight: 0.087
    examples:
      - "Customer called to inquire about their monthly billing statement and wanted clarification on specific charges."
      - "Customer disputed several charges on their account and requested a detailed breakdown of fees."
      - "Customer needed help understanding their billing cycle and payment due dates."
  - id: 1
    name: "technical_support"
    count: 38
    representation: "technical issue problem connection internet"
    words:
      - word: "technical"
        weight: 0.178
      - word: "issue"
        weight: 0.145
      - word: "problem"
        weight: 0.132
      - word: "connection"
        weight: 0.119
      - word: "internet"
        weight: 0.106
      - word: "troubleshoot"
        weight: 0.094
    examples:
      - "Customer experiencing slow internet connection and needs technical assistance to resolve the issue."
      - "Customer's email setup is not working correctly and requires technical support guidance."
      - "Customer cannot access their online account and needs help with login troubleshooting."
  - id: 2
    name: "service_cancellation"
    count: 32
    representation: "cancel service termination account close"
    words:
      - word: "cancel"
        weight: 0.189
      - word: "service"
        weight: 0.167
      - word: "termination"
        weight: 0.145
      - word: "account"
        weight: 0.123
      - word: "close"
        weight: 0.111
      - word: "discontinue"
        weight: 0.089
    examples:
      - "Customer wants to cancel their service due to moving to a new location outside coverage area."
      - "Customer is dissatisfied with service quality and wishes to terminate their account."
      - "Customer received a better offer from competitor and wants to cancel current service."
  - id: 3
    name: "product_information"
    count: 28
    representation: "product features upgrade plan pricing"
    words:
      - word: "product"
        weight: 0.172
      - word: "features"
        weight: 0.156
      - word: "upgrade"
        weight: 0.143
      - word: "plan"
        weight: 0.129
      - word: "pricing"
        weight: 0.115
      - word: "options"
        weight: 0.098
    examples:
      - "Customer inquired about upgrading to a higher-tier service plan with additional features."
      - "Customer asked for detailed information about product features and pricing options."
      - "Customer wanted to compare different service plans to find the best fit for their needs."
visualization_notes:
  topics_visualization: "Topic distribution chart shows 4 main topics with billing inquiries being most common"
  heatmap_visualization: "Topic-word heatmap reveals clear semantic clusters"
  available_files: "topics_chart.png, topic_heatmap.png"
debug_info:
  transformed_text_lines_count: 245
  unique_lines_count: 238
  repetition_detected: false
block_title: "Topic Analysis"`;

export default function TopicAnalysisPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <MessageCircle className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">TopicAnalysis</h1>
          <Badge variant="secondary">NLP</Badge>
        </div>
        <p className="text-lg text-muted-foreground leading-relaxed">
          The TopicAnalysis report block performs NLP analysis to identify and categorize topics in text data 
          using BERTopic. It processes transcript data through various transformation methods and generates 
          comprehensive topic insights with visualizations and representative examples.
        </p>
      </div>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Overview</h2>
          <div className="space-y-4 text-muted-foreground">
            <p>
              The TopicAnalysis block orchestrates a multi-stage analysis pipeline similar to the 
              <code className="text-sm bg-muted px-1 py-0.5 rounded">plexus analyze topics</code> CLI command. 
              It transforms text data, applies BERTopic clustering to discover topics, and generates 
              visualizations and insights.
            </p>
            <p>
              The analysis supports multiple transformation methods including direct chunking, LLM-based 
              extraction, and itemized processing, making it flexible for different types of text data 
              and analysis requirements.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Features</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex items-start gap-3">
              <Brain className="h-5 w-5 text-primary mt-1" />
              <div>
                <h3 className="font-medium">BERTopic Clustering</h3>
                <p className="text-sm text-muted-foreground">
                  Advanced topic modeling using state-of-the-art transformer embeddings
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <PieChart className="h-5 w-5 text-primary mt-1" />
              <div>
                <h3 className="font-medium">Topic Visualization</h3>
                <p className="text-sm text-muted-foreground">
                  Interactive charts showing topic distribution and relationships
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <TrendingUp className="h-5 w-5 text-primary mt-1" />
              <div>
                <h3 className="font-medium">Keyword Extraction</h3>
                <p className="text-sm text-muted-foreground">
                  Identifies most relevant keywords for each discovered topic
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <FileText className="h-5 w-5 text-primary mt-1" />
              <div>
                <h3 className="font-medium">Representative Examples</h3>
                <p className="text-sm text-muted-foreground">
                  Shows actual text examples that best represent each topic
                </p>
              </div>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Configuration</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground">
              Configure the TopicAnalysis block in your report configuration:
            </p>
            <div className="bg-muted p-4 rounded-lg font-mono text-sm">
              <div className="text-foreground">```block name="Topic Analysis"</div>
              <div className="text-foreground">class: TopicAnalysis</div>
              <div className="text-foreground">data:</div>
              <div className="text-foreground">  source: "customer-calls"      # DataSource name or ID</div>
              <div className="text-foreground">  content_column: "text"        # Column containing text data</div>
              <div className="text-foreground">  sample_size: 1000             # Optional: limit number of records</div>
              <div className="text-foreground">llm_extraction:</div>
              <div className="text-foreground">  method: "chunk"               # "chunk", "llm", or "itemize"</div>
              <div className="text-foreground">  provider: "ollama"            # LLM provider if using "llm" method</div>
              <div className="text-foreground">  model: "gemma3:27b"           # LLM model if using "llm" method</div>
              <div className="text-foreground">bertopic_analysis:</div>
              <div className="text-foreground">  min_topic_size: 10            # Minimum documents per topic</div>
              <div className="text-foreground">  top_n_words: 10               # Number of keywords per topic</div>
              <div className="text-foreground">```</div>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Configuration Parameters</h2>
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium mb-3">Data Configuration</h3>
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left p-3 font-medium">Parameter</th>
                      <th className="text-left p-3 font-medium">Required</th>
                      <th className="text-left p-3 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    <tr>
                      <td className="p-3 font-mono text-xs">data.source</td>
                      <td className="p-3">
                        <Badge variant="destructive" className="text-xs">Required*</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        DataSource name, key, or ID (mutually exclusive with dataset)
                      </td>
                    </tr>
                    <tr>
                      <td className="p-3 font-mono text-xs">data.dataset</td>
                      <td className="p-3">
                        <Badge variant="destructive" className="text-xs">Required*</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        Specific DataSet ID (mutually exclusive with source)
                      </td>
                    </tr>
                    <tr>
                      <td className="p-3 font-mono text-xs">data.content_column</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="text-xs">Optional</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        Column containing text data (default: "text")
                      </td>
                    </tr>
                    <tr>
                      <td className="p-3 font-mono text-xs">data.sample_size</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="text-xs">Optional</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        Limit number of records to process (default: all)
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted-foreground mt-2">* Either source OR dataset must be specified</p>
            </div>

            <div>
              <h3 className="text-lg font-medium mb-3">LLM Extraction Configuration</h3>
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left p-3 font-medium">Parameter</th>
                      <th className="text-left p-3 font-medium">Required</th>
                      <th className="text-left p-3 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    <tr>
                      <td className="p-3 font-mono text-xs">llm_extraction.method</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="text-xs">Optional</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        "chunk", "llm", or "itemize" (default: "chunk")
                      </td>
                    </tr>
                    <tr>
                      <td className="p-3 font-mono text-xs">llm_extraction.provider</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="text-xs">Optional</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        "ollama", "openai", "anthropic" (default: "ollama")
                      </td>
                    </tr>
                    <tr>
                      <td className="p-3 font-mono text-xs">llm_extraction.model</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="text-xs">Optional</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        LLM model name (default: "gemma3:27b")
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-medium mb-3">BERTopic Analysis Configuration</h3>
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left p-3 font-medium">Parameter</th>
                      <th className="text-left p-3 font-medium">Required</th>
                      <th className="text-left p-3 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    <tr>
                      <td className="p-3 font-mono text-xs">bertopic_analysis.min_topic_size</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="text-xs">Optional</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        Minimum documents per topic (default: 10)
                      </td>
                    </tr>
                    <tr>
                      <td className="p-3 font-mono text-xs">bertopic_analysis.top_n_words</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="text-xs">Optional</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        Number of keywords per topic (default: 10)
                      </td>
                    </tr>
                    <tr>
                      <td className="p-3 font-mono text-xs">bertopic_analysis.min_ngram</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="text-xs">Optional</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        Minimum n-gram size (default: 1)
                      </td>
                    </tr>
                    <tr>
                      <td className="p-3 font-mono text-xs">bertopic_analysis.max_ngram</td>
                      <td className="p-3">
                        <Badge variant="secondary" className="text-xs">Optional</Badge>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        Maximum n-gram size (default: 2)
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Example Output</h2>
          <p className="text-muted-foreground mb-4">
            Here's an example of how the TopicAnalysis block output appears in a report:
          </p>
          <Card className="border-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageCircle className="h-5 w-5" />
                Live Example
              </CardTitle>
              <CardDescription>
                This is a live rendering of the TopicAnalysis component using example data
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="border-t">
                <TopicAnalysis 
                  output={exampleOutput}
                  name="Topic Analysis Example"
                  type="TopicAnalysis"
                />
              </div>
            </CardContent>
          </Card>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding the Output</h2>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Topic Discovery</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    BERTopic automatically discovers the optimal number of topics based on the data, 
                    clustering semantically similar texts together. Each topic is characterized by 
                    its most representative keywords and examples.
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Pipeline Visualization</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    The pipeline diagram shows the complete flow from data preprocessing through 
                    LLM extraction to BERTopic analysis, making it easy to understand and 
                    reproduce the analysis process.
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Topic Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Interactive pie chart visualization shows the relative prevalence of each topic, 
                    helping identify the most common themes in your data at a glance.
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Representative Examples</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Each topic includes actual text examples that best represent the topic's content, 
                    providing concrete context for understanding what each topic covers.
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Analysis Methods</h2>
          <div className="space-y-4">
            <div className="grid gap-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Code className="h-4 w-4" />
                    Chunking Method
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-2">
                    Direct text chunking without LLM processing. Fast and efficient for well-structured text data.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    <strong>Best for:</strong> Clean transcript data, structured documents, high-volume processing
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Brain className="h-4 w-4" />
                    LLM Method
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-2">
                    Uses large language models to extract and refine key themes from text before topic analysis.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    <strong>Best for:</strong> Noisy data, complex conversations, extracting specific themes
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Itemize Method
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-2">
                    Breaks down text into individual items or points using LLM analysis for granular topic discovery.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    <strong>Best for:</strong> Multi-topic documents, detailed analysis, customer feedback
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <section className="bg-muted/50 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Related Documentation
          </h3>
          <div className="space-y-2">
            <Link href="/documentation/concepts/reports" className="block text-primary hover:text-primary/80">
              Reports Concept Overview →
            </Link>
            <Link href="/documentation/advanced/cli" className="block text-primary hover:text-primary/80">
              CLI Topic Analysis Commands →
            </Link>
            <Link href="/documentation/report-blocks" className="block text-primary hover:text-primary/80">
              ← Back to Report Blocks
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
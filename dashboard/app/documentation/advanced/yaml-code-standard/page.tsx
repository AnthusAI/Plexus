'use client';

import { MessageSquareCode } from 'lucide-react';
import { CodeSnippet } from '@/components/ui/code-snippet';
import FeedbackAnalysis from '@/components/blocks/FeedbackAnalysis';

export default function YAMLCodeStandardPage() {
  // Create the YAML data but also parse it into the object structure for the component
  const sampleYAMLCode = `# Feedback Analysis Report Output
# 
# This is the structured output from a feedback analysis process that:
# 1. Retrieves feedback items from scorecards within a specified time range
# 2. Analyzes agreement between initial and final answer values using Gwet's AC1 coefficient
# 3. Provides statistical measures of inter-rater reliability and agreement
# 4. Generates insights about feedback quality and consistency across evaluators
#
# The output contains agreement scores, statistical measures, detailed breakdowns,
# and analytical insights for understanding feedback consistency and reliability.

overall_ac1: 0.847
total_items: 2847
total_mismatches: 436
total_agreements: 2411
accuracy: 84.7
total_feedback_items_retrieved: 2847
date_range:
  start: "2024-01-01T00:00:00"
  end: "2024-01-31T23:59:59"
message: "Processed 4 score(s)."
classes_count: 2
label_distribution:
  "Yes": 1523
  "No": 1324
confusion_matrix:
  labels: ["Yes", "No"]
  matrix:
    - actualClassLabel: "Yes"
      predictedClassCounts:
        "Yes": 1287
        "No": 236
    - actualClassLabel: "No"
      predictedClassCounts:
        "Yes": 200
        "No": 1124
class_distribution:
  - label: "Yes"
    count: 1523
  - label: "No"
    count: 1324
predicted_class_distribution:
  - label: "Yes"
    count: 1487
  - label: "No"
    count: 1360
precision: 86.5
recall: 84.5
warning: null
warnings: null
notes: null
discussion: null
block_title: "Feedback Analysis"
block_description: "Inter-rater Reliability Assessment"

scores:
  - score_id: "44246"
    score_name: "Agent followed greeting protocol"
    cc_question_id: "1234"
    ac1: 0.923
    item_count: 856
    mismatches: 66
    agreements: 790
    accuracy: 92.3
    classes_count: 2
    label_distribution:
      "Yes": 634
      "No": 222
    confusion_matrix:
      labels: ["Yes", "No"]
      matrix:
        - actualClassLabel: "Yes"
          predictedClassCounts:
            "Yes": 590
            "No": 44
        - actualClassLabel: "No"
          predictedClassCounts:
            "Yes": 22
            "No": 200
    class_distribution:
      - label: "Yes"
        count: 634
      - label: "No" 
        count: 222
    predicted_class_distribution:
      - label: "Yes"
        count: 612
      - label: "No"
        count: 244
    precision: 96.4
    recall: 93.1
    warning: null
    warnings: null
    notes: null
    discussion: null
    indexed_items_file: "feedback_analysis_44246_items.json"
    
  - score_id: "44247"
    score_name: "Agent provided accurate information"
    cc_question_id: "1235"
    ac1: 0.784
    item_count: 743
    mismatches: 160
    agreements: 583
    accuracy: 78.4
    classes_count: 2
    label_distribution:
      "Yes": 421
      "No": 322
    confusion_matrix:
      labels: ["Yes", "No"]
      matrix:
        - actualClassLabel: "Yes"
          predictedClassCounts:
            "Yes": 321
            "No": 100
        - actualClassLabel: "No"
          predictedClassCounts:
            "Yes": 60
            "No": 262
    class_distribution:
      - label: "Yes"
        count: 421
      - label: "No"
        count: 322
    predicted_class_distribution:
      - label: "Yes"
        count: 381
      - label: "No"
        count: 362
    precision: 84.3
    recall: 76.2
    warning: "Lower than expected agreement - consider reviewer training"
    warnings: "Lower than expected agreement - consider reviewer training"
    notes: null
    discussion: null
    indexed_items_file: "feedback_analysis_44247_items.json"
    
  - score_id: "44248"
    score_name: "Call resolution was complete"
    cc_question_id: "1236"
    ac1: 0.867
    item_count: 692
    mismatches: 92
    agreements: 600
    accuracy: 86.7
    classes_count: 2
    label_distribution:
      "Yes": 412
      "No": 280
    confusion_matrix:
      labels: ["Yes", "No"]
      matrix:
        - actualClassLabel: "Yes"
          predictedClassCounts:
            "Yes": 356
            "No": 56
        - actualClassLabel: "No"
          predictedClassCounts:
            "Yes": 36
            "No": 244
    class_distribution:
      - label: "Yes"
        count: 412
      - label: "No"
        count: 280
    predicted_class_distribution:
      - label: "Yes"
        count: 392
      - label: "No"
        count: 300
    precision: 90.8
    recall: 86.4
    warning: null
    warnings: null
    notes: null
    discussion: null
    indexed_items_file: "feedback_analysis_44248_items.json"
    
  - score_id: "44249"
    score_name: "Customer satisfaction achieved"
    cc_question_id: "1237"
    ac1: 0.634
    item_count: 556
    mismatches: 118
    agreements: 438
    accuracy: 63.4
    classes_count: 2
    label_distribution:
      "Yes": 256
      "No": 300
    confusion_matrix:
      labels: ["Yes", "No"]
      matrix:
        - actualClassLabel: "Yes"
          predictedClassCounts:
            "Yes": 178
            "No": 78
        - actualClassLabel: "No"
          predictedClassCounts:
            "Yes": 40
            "No": 260
    class_distribution:
      - label: "Yes"
        count: 256
      - label: "No"
        count: 300
    predicted_class_distribution:
      - label: "Yes"
        count: 218
      - label: "No"
        count: 338
    precision: 81.7
    recall: 69.5
    warning: "Critical: Low agreement on customer satisfaction scores - systematic disagreement detected"
    warnings: "Critical: Low agreement on customer satisfaction scores - systematic disagreement detected"
    notes: null
    discussion: "The customer satisfaction scoring shows concerning patterns with only 63.4% agreement between reviewers. This suggests either unclear scoring criteria, subjective interpretation differences, or inconsistent training. The confusion matrix reveals reviewers frequently disagree on borderline cases. Recommended actions: 1) Review and clarify customer satisfaction scoring rubric, 2) Conduct calibration sessions with reviewers, 3) Add more specific behavioral indicators for satisfaction levels, 4) Consider inter-rater reliability training focused on customer satisfaction assessment."
    indexed_items_file: "feedback_analysis_44249_items.json"`;


  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <div className="mb-6">
        <h1 className="text-4xl font-bold">Universal Code Snippets</h1>
        <p className="text-lg text-muted-foreground">
          Universal code interface for humans, AI models, and systems
        </p>
      </div>

      <div className="space-y-8">
        <section className="relative">
          <h2 className="text-2xl font-semibold mb-4">The Universal Code Icon</h2>
          {/* Oversized icon positioned at top-right of this section */}
          <div className="absolute top-0 right-0">
            <MessageSquareCode className="h-16 w-16 md:h-20 md:w-20 lg:h-24 lg:w-24 text-primary/20" />
          </div>
          <div className="space-y-4 pr-20 md:pr-24 lg:pr-28">
            <p className="text-muted-foreground">
              Throughout Plexus, this icon means you can grab structured data that works everywhere. Click it, copy the output, 
              and paste it directly into ChatGPT, Claude, your code editor, or share it with other team members. 
              The YAML format includes built-in context so anyone (human or AI) immediately understands what they're looking at.
            </p>
            <p className="text-muted-foreground">
              No more wrestling with dense JSON or losing context when you move data between tools. 
              It just works, everywhere.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Visual Report → Universal Code</h2>
          <p className="text-muted-foreground mb-6">
            Here's how it works: every graphical report in Plexus has a corresponding code representation. 
            Below is a real call center feedback analysis report. The visual report displays agreement scores, confusion matrices, and insights beautifully. 
            The Code button reveals the same data as contextual YAML that works everywhere.
          </p>

          <div className="p-4 bg-violet-50 dark:bg-violet-950/40 rounded-lg border-l-4 border-violet-500 mb-6">
            <h3 className="text-lg font-semibold mb-2">Try the Code Button</h3>
            <p className="text-muted-foreground">
              Use the Code button in the top-right to see how visual insights transform into structured YAML that works with any AI tool, documentation system, or code repository.
            </p>
          </div>

          <div>
            <div className="flex justify-end mb-2">
              <div className="flex flex-col items-center">
                <div className="text-sm text-muted-foreground font-medium mb-1">Universal Code</div>
                <div className="text-muted-foreground text-3xl font-black animate-attention-bounce">↓</div>
              </div>
            </div>
            <div className="rounded-lg p-4 bg-frame">
              <FeedbackAnalysis
                config={{}}
                output={sampleYAMLCode}
                position={1}
                type="FeedbackAnalysis"
                id="call-center-feedback-example"
                name="Call Center Quality Feedback Analysis"
                className="border-0 p-0"
              />
            </div>
          </div>

          <div className="bg-muted/30 p-4 rounded-lg mt-6">
            <p className="text-sm text-muted-foreground">
              💡 <strong>Try this:</strong> Use the Code button to reveal contextual YAML with explanatory comments. 
              Click the Copy button to copy the code to your clipboard. 
              Paste it into ChatGPT or Claude and ask: "Which call center scores show the highest disagreement between reviewers?" or "What training recommendations would improve inter-rater reliability?" 
              The AI will immediately understand the context and give you strategic recommendations.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Available Everywhere</h2>
          <p className="text-muted-foreground mb-6">
            Every report block in Plexus automatically generates Universal Code Snippets. Whether you're working with 
            topic analysis, feedback analysis, confusion matrices, or any other analytical output, the distinctive 
            code icon gives you instant access to structured, contextual data.
          </p>
          
          <p className="text-muted-foreground mb-6">
            You'll also find Universal Code Snippets in:
          </p>
          
          <div className="grid md:grid-cols-2 gap-4">
            <div className="p-4 bg-card rounded-lg border">
              <h3 className="font-medium mb-2">📊 Report Blocks</h3>
              <p className="text-sm text-muted-foreground">
                Every analytical output includes the Universal Code Icon for instant data access
              </p>
            </div>
            <div className="p-4 bg-card rounded-lg border">
              <h3 className="font-medium mb-2">🎯 Evaluations</h3>
              <p className="text-sm text-muted-foreground">
                Evaluation results with confusion matrices, accuracy metrics, and performance data
              </p>
            </div>
            <div className="p-4 bg-card rounded-lg border">
              <h3 className="font-medium mb-2">📈 Analytics</h3>
              <p className="text-sm text-muted-foreground">
                Statistical analysis, agreement scores, and performance insights
              </p>
            </div>
            <div className="p-4 bg-card rounded-lg border">
              <h3 className="font-medium mb-2">🔧 Configurations</h3>
              <p className="text-sm text-muted-foreground">
                Scorecard and score configurations exported in universal format
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Why This Matters</h2>
          <p className="text-muted-foreground mb-4">
            Traditional data exports lack context when you move them around. 
            Universal Code Snippets solve this by packaging your data with built-in explanations that travel with it.
          </p>
          <p className="text-muted-foreground">
            This means you can seamlessly move insights between Plexus, your AI tools, documentation, code repositories, 
            and team conversations without losing meaning or requiring additional explanation.
          </p>
        </section>
      </div>
    </div>
  );
}
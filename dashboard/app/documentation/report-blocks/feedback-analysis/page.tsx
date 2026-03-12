"use client"

import { Button as DocButton } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import Link from "next/link"
import { BarChart3, Code, FileText, TrendingUp, AlertCircle } from 'lucide-react'
import FeedbackAnalysis from '@/components/blocks/FeedbackAnalysis'

// Example output data that matches the actual structure from the FeedbackAnalysis block
const exampleOutput = `# Feedback Analysis Report Output
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
total_items: 156
total_mismatches: 24
total_agreements: 132
accuracy: 84.62
scores:
  - score_id: score_123
    score_name: "Call Quality Assessment"
    cc_question_id: "1438_1"
    ac1: 0.823
    item_count: 78
    mismatches: 14
    agreements: 64
    accuracy: 82.05
    classes_count: 2
    label_distribution:
      "Yes": 45
      "No": 33
    confusion_matrix:
      true_labels: ["Yes", "No"]
      predicted_labels: ["Yes", "No"]
      matrix:
        - [42, 3]
        - [11, 22]
    precision: 79.25
    recall: 93.33
    warning: null
  - score_id: score_124
    score_name: "Resolution Effectiveness"
    cc_question_id: "1438_2"
    ac1: 0.871
    item_count: 78
    mismatches: 10
    agreements: 68
    accuracy: 87.18
    classes_count: 2
    label_distribution:
      "Effective": 52
      "Ineffective": 26
    confusion_matrix:
      true_labels: ["Effective", "Ineffective"]
      predicted_labels: ["Effective", "Ineffective"]
      matrix:
        - [48, 4]
        - [6, 20]
    precision: 88.89
    recall: 92.31
    warning: null
total_feedback_items_retrieved: 156
date_range:
  start: "2024-01-01T00:00:00+00:00"
  end: "2024-01-31T23:59:59.999999+00:00"
message: "Processed 2 score(s)."
classes_count: 2
label_distribution:
  "Yes": 45
  "No": 33
  "Effective": 52
  "Ineffective": 26
confusion_matrix:
  true_labels: ["Yes", "No", "Effective", "Ineffective"]
  predicted_labels: ["Yes", "No", "Effective", "Ineffective"]
  matrix:
    - [42, 3, 0, 0]
    - [11, 22, 0, 0]
    - [0, 0, 48, 4]
    - [0, 0, 6, 20]
precision: 84.07
recall: 92.82
warning: null
block_title: "Feedback Analysis"
block_description: "Inter-rater Reliability Assessment"`;

export default function FeedbackAnalysisPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <BarChart3 className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">FeedbackAnalysis</h1>
          <Badge variant="secondary">Analytics</Badge>
        </div>
        <p className="text-lg text-muted-foreground leading-relaxed">
          The FeedbackAnalysis report block analyzes feedback data and calculates inter-rater reliability 
          using Gwet's AC1 agreement coefficient. It provides comprehensive insights into agreement between 
          evaluators and helps assess the quality and consistency of feedback data.
        </p>
      </div>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Overview</h2>
          <div className="space-y-4 text-muted-foreground">
            <p>
              The FeedbackAnalysis block retrieves FeedbackItem records and compares initial and final 
              answer values to calculate agreement scores using Gwet's AC1 coefficient. This provides 
              a robust measure of inter-rater reliability that accounts for chance agreement.
            </p>
            <p>
              The analysis can focus on a specific score or analyze all scores associated with a scorecard, 
              providing both individual score breakdowns and overall aggregated metrics.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Features</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex items-start gap-3">
              <TrendingUp className="h-5 w-5 text-primary mt-1" />
              <div>
                <h3 className="font-medium">AC1 Agreement Coefficient</h3>
                <p className="text-sm text-muted-foreground">
                  Calculates Gwet's AC1 for robust inter-rater reliability measurement
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <BarChart3 className="h-5 w-5 text-primary mt-1" />
              <div>
                <h3 className="font-medium">Accuracy Metrics</h3>
                <p className="text-sm text-muted-foreground">
                  Provides accuracy, precision, and recall measurements
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <FileText className="h-5 w-5 text-primary mt-1" />
              <div>
                <h3 className="font-medium">Detailed Breakdowns</h3>
                <p className="text-sm text-muted-foreground">
                  Score-by-score analysis with confusion matrices
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-primary mt-1" />
              <div>
                <h3 className="font-medium">Quality Insights</h3>
                <p className="text-sm text-muted-foreground">
                  Automatic warnings for data quality issues
                </p>
              </div>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Configuration</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground">
              Configure the FeedbackAnalysis block in your report configuration:
            </p>
            <div className="bg-muted p-4 rounded-lg font-mono text-sm">
              <div className="text-foreground">```block</div>
              <div className="text-foreground">class: FeedbackAnalysis</div>
              <div className="text-foreground">scorecard: "1438"          # Required: Call Criteria Scorecard ID</div>
              <div className="text-foreground">days: 30                   # Optional: Number of days to analyze (default: 14)</div>
              <div className="text-foreground">start_date: "2024-01-01"   # Optional: Start date (YYYY-MM-DD format)</div>
              <div className="text-foreground">end_date: "2024-01-31"     # Optional: End date (YYYY-MM-DD format)</div>
              <div className="text-foreground">score_id: "1438_1"         # Optional: Specific score ID to analyze</div>
              <div className="text-foreground">```</div>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Configuration Parameters</h2>
          <div className="space-y-4">
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
                    <td className="p-3 font-mono text-xs">scorecard</td>
                    <td className="p-3">
                      <Badge variant="destructive" className="text-xs">Required</Badge>
                    </td>
                    <td className="p-3 text-muted-foreground">
                      Call Criteria Scorecard ID to analyze
                    </td>
                  </tr>
                  <tr>
                    <td className="p-3 font-mono text-xs">days</td>
                    <td className="p-3">
                      <Badge variant="secondary" className="text-xs">Optional</Badge>
                    </td>
                    <td className="p-3 text-muted-foreground">
                      Number of days in the past to analyze (default: 14)
                    </td>
                  </tr>
                  <tr>
                    <td className="p-3 font-mono text-xs">start_date</td>
                    <td className="p-3">
                      <Badge variant="secondary" className="text-xs">Optional</Badge>
                    </td>
                    <td className="p-3 text-muted-foreground">
                      Start date for analysis (YYYY-MM-DD format, overrides days)
                    </td>
                  </tr>
                  <tr>
                    <td className="p-3 font-mono text-xs">end_date</td>
                    <td className="p-3">
                      <Badge variant="secondary" className="text-xs">Optional</Badge>
                    </td>
                    <td className="p-3 text-muted-foreground">
                      End date for analysis (YYYY-MM-DD format, defaults to today)
                    </td>
                  </tr>
                  <tr>
                    <td className="p-3 font-mono text-xs">score_id</td>
                    <td className="p-3">
                      <Badge variant="secondary" className="text-xs">Optional</Badge>
                    </td>
                    <td className="p-3 text-muted-foreground">
                      Specific Call Criteria Question ID to analyze (analyzes all if omitted)
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Example Output</h2>
          <p className="text-muted-foreground mb-4">
            Here's an example of how the FeedbackAnalysis block output appears in a report:
          </p>
          <Card className="border-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Live Example
              </CardTitle>
              <CardDescription>
                This is a live rendering of the FeedbackAnalysis component using example data
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="border-t">
                <FeedbackAnalysis 
                  output={exampleOutput}
                  name="Feedback Analysis Example"
                  type="FeedbackAnalysis"
                  config={{}}
                  position={0}
                  id="feedback-analysis-example"
                />
              </div>
            </CardContent>
          </Card>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding the Metrics</h2>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">AC1 Coefficient</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Gwet's AC1 is a chance-corrected agreement coefficient that's more robust than 
                    Cohen's kappa, especially for imbalanced data. Values range from -1 to 1, 
                    with higher values indicating better agreement.
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Accuracy</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    The percentage of feedback items where the initial and final answers agree. 
                    This provides a straightforward measure of evaluator consistency.
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Precision & Recall</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Precision measures the accuracy of positive predictions, while recall measures 
                    the ability to find all positive instances. These help understand performance 
                    across different response categories.
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Confusion Matrix</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Shows the detailed breakdown of agreements and disagreements between initial 
                    and final answers, helping identify specific patterns in evaluator behavior.
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
            <Link href="/documentation/evaluation-metrics" className="block text-primary hover:text-primary/80">
              Understanding Evaluation Metrics →
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
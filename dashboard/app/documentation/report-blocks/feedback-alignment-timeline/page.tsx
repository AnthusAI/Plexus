"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import FeedbackAlignmentTimeline from "@/components/blocks/FeedbackAlignmentTimeline";
import { LineChart } from "lucide-react";

const sampleOutput = {
  mode: "all_scores",
  block_title: "Feedback Alignment Timeline",
  block_description: "Alignment metrics over complete historical time buckets",
  scorecard_id: "scorecard-1438",
  scorecard_name: "Quality Scorecard",
  bucket_policy: {
    bucket_type: "calendar_week",
    bucket_count: 6,
    timezone: "UTC",
    week_start: "monday",
    complete_only: true,
  },
  date_range: {
    start: "2026-02-23T00:00:00+00:00",
    end: "2026-04-06T00:00:00+00:00",
  },
  overall: {
    score_id: "overall",
    score_name: "Overall",
    points: [
      { bucket_index: 0, label: "2026-02-23", start: "2026-02-23T00:00:00+00:00", end: "2026-03-02T00:00:00+00:00", ac1: 0.74, accuracy: 82.5, item_count: 40, agreements: 33, mismatches: 7 },
      { bucket_index: 1, label: "2026-03-02", start: "2026-03-02T00:00:00+00:00", end: "2026-03-09T00:00:00+00:00", ac1: 0.7, accuracy: 80.0, item_count: 35, agreements: 28, mismatches: 7 },
      { bucket_index: 2, label: "2026-03-09", start: "2026-03-09T00:00:00+00:00", end: "2026-03-16T00:00:00+00:00", ac1: 0.68, accuracy: 78.3, item_count: 46, agreements: 36, mismatches: 10 },
      { bucket_index: 3, label: "2026-03-16", start: "2026-03-16T00:00:00+00:00", end: "2026-03-23T00:00:00+00:00", ac1: 0.8, accuracy: 86.4, item_count: 44, agreements: 38, mismatches: 6 },
      { bucket_index: 4, label: "2026-03-23", start: "2026-03-23T00:00:00+00:00", end: "2026-03-30T00:00:00+00:00", ac1: 0.83, accuracy: 88.6, item_count: 35, agreements: 31, mismatches: 4 },
      { bucket_index: 5, label: "2026-03-30", start: "2026-03-30T00:00:00+00:00", end: "2026-04-06T00:00:00+00:00", ac1: null, accuracy: null, item_count: 0, agreements: 0, mismatches: 0 },
    ],
  },
  scores: [
    {
      score_id: "score-1",
      score_name: "Empathy",
      points: [
        { bucket_index: 0, label: "2026-02-23", start: "2026-02-23T00:00:00+00:00", end: "2026-03-02T00:00:00+00:00", ac1: 0.81, accuracy: 89.4, item_count: 19, agreements: 17, mismatches: 2 },
        { bucket_index: 1, label: "2026-03-02", start: "2026-03-02T00:00:00+00:00", end: "2026-03-09T00:00:00+00:00", ac1: 0.76, accuracy: 84.2, item_count: 19, agreements: 16, mismatches: 3 },
        { bucket_index: 2, label: "2026-03-09", start: "2026-03-09T00:00:00+00:00", end: "2026-03-16T00:00:00+00:00", ac1: 0.72, accuracy: 81.0, item_count: 21, agreements: 17, mismatches: 4 },
        { bucket_index: 3, label: "2026-03-16", start: "2026-03-16T00:00:00+00:00", end: "2026-03-23T00:00:00+00:00", ac1: 0.79, accuracy: 86.4, item_count: 22, agreements: 19, mismatches: 3 },
        { bucket_index: 4, label: "2026-03-23", start: "2026-03-23T00:00:00+00:00", end: "2026-03-30T00:00:00+00:00", ac1: 0.88, accuracy: 92.3, item_count: 13, agreements: 12, mismatches: 1 },
        { bucket_index: 5, label: "2026-03-30", start: "2026-03-30T00:00:00+00:00", end: "2026-04-06T00:00:00+00:00", ac1: null, accuracy: null, item_count: 0, agreements: 0, mismatches: 0 },
      ],
    },
    {
      score_id: "score-2",
      score_name: "Resolution",
      points: [
        { bucket_index: 0, label: "2026-02-23", start: "2026-02-23T00:00:00+00:00", end: "2026-03-02T00:00:00+00:00", ac1: 0.66, accuracy: 76.2, item_count: 21, agreements: 16, mismatches: 5 },
        { bucket_index: 1, label: "2026-03-02", start: "2026-03-02T00:00:00+00:00", end: "2026-03-09T00:00:00+00:00", ac1: 0.64, accuracy: 75.0, item_count: 16, agreements: 12, mismatches: 4 },
        { bucket_index: 2, label: "2026-03-09", start: "2026-03-09T00:00:00+00:00", end: "2026-03-16T00:00:00+00:00", ac1: 0.61, accuracy: 74.0, item_count: 25, agreements: 19, mismatches: 6 },
        { bucket_index: 3, label: "2026-03-16", start: "2026-03-16T00:00:00+00:00", end: "2026-03-23T00:00:00+00:00", ac1: 0.81, accuracy: 86.4, item_count: 22, agreements: 19, mismatches: 3 },
        { bucket_index: 4, label: "2026-03-23", start: "2026-03-23T00:00:00+00:00", end: "2026-03-30T00:00:00+00:00", ac1: 0.78, accuracy: 86.4, item_count: 22, agreements: 19, mismatches: 3 },
        { bucket_index: 5, label: "2026-03-30", start: "2026-03-30T00:00:00+00:00", end: "2026-04-06T00:00:00+00:00", ac1: null, accuracy: null, item_count: 0, agreements: 0, mismatches: 0 },
      ],
    },
  ],
  total_feedback_items_retrieved: 200,
  message: "Processed 2 score(s) across 6 complete bucket(s).",
};

export default function FeedbackAlignmentTimelinePage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6 space-y-8">
      <div>
        <div className="flex items-center gap-3 mb-3">
          <LineChart className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">FeedbackAlignmentTimeline</h1>
          <Badge variant="secondary">Trend</Badge>
        </div>
        <p className="text-lg text-muted-foreground">
          Tracks feedback alignment change over time using complete historical buckets.
          Plots AC1 as a horizontal time-series, supports overall/per-score trends, and includes an expandable
          per-bucket details section with AC1/Accuracy gauges and raw agreement bars.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
          <CardDescription>Example block configuration</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="text-xs bg-muted rounded p-3 overflow-x-auto"><code>{`class: FeedbackAlignmentTimeline
scorecard: "1438"
# Optional: analyze one score only
# score: "1438_1"
bucket_type: calendar_week
bucket_count: 12
timezone: UTC
week_start: monday`}</code></pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Supported Bucket Types</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-1">
          <p>`trailing_1d`, `trailing_7d`, `trailing_14d`, `trailing_30d`</p>
          <p>`calendar_day`, `calendar_week`, `calendar_biweek`, `calendar_month`</p>
          <p>All policies include complete previous periods only.</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bucket Details Panel</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-1">
          <p>The chart includes an always-visible <strong>Bucket Details</strong> list under the visualization.</p>
          <p>Each bucket row shows AC1 and Accuracy gauges, raw agreement, and item counts.</p>
          <p>Rows with no data are explicitly marked so empty periods are easy to spot.</p>
        </CardContent>
      </Card>

      <Card className="border-2">
        <CardHeader>
          <CardTitle>Live Example</CardTitle>
          <CardDescription>Rendered component with sample output</CardDescription>
        </CardHeader>
        <CardContent className="p-0 border-t">
          <FeedbackAlignmentTimeline
            output={sampleOutput}
            name="Feedback Alignment Timeline Example"
            type="FeedbackAlignmentTimeline"
            config={{}}
            position={0}
            id="feedback-alignment-timeline-example"
          />
        </CardContent>
      </Card>
    </div>
  );
}

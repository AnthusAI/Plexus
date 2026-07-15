import type { Meta, StoryObj } from "@storybook/react";
import { BlockRenderer } from "@/components/blocks/BlockRegistry";

const meta: Meta<typeof BlockRenderer> = {
  title: "Reports/Blocks/FeedbackAlignmentTimeline",
  component: BlockRenderer,
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component:
          "Explains stored feedback alignment semantics, then renders the overall AC1 timeline plus a separate AC1 timeline for each included score using rolling minimum samples.",
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof BlockRenderer>;

const baseOutput = {
  mode: "all_scores",
  block_title: "Feedback Alignment Timeline",
  block_description: "Alignment metrics over complete historical time buckets",
  bucket_policy: {
    bucket_type: "trailing_7d",
    bucket_count: 6,
    timezone: "UTC",
    week_start: "monday",
    complete_only: true,
  },
  sample_policy: {
    rolling_min_items: 100,
    lookback: "unbounded",
    bucket_timestamp: "FeedbackItem.editedAt",
    prediction_value: "FeedbackItem.initialAnswerValue",
    reference_value: "FeedbackItem.finalAnswerValue",
  },
  overall: {
    score_id: "overall",
    score_name: "Overall",
    points: [
      { bucket_index: 0, label: "2026-02-23", start: "2026-02-23T00:00:00+00:00", end: "2026-03-02T00:00:00+00:00", ac1: 0.62, accuracy: 75, item_count: 100, bucket_item_count: 20, sample_item_count: 100, lookback_item_count: 80, sample_start: "2026-01-10T00:00:00+00:00", sample_end: "2026-03-01T18:00:00+00:00", sample_extended: true, agreements: 75, mismatches: 25 },
      { bucket_index: 1, label: "2026-03-02", start: "2026-03-02T00:00:00+00:00", end: "2026-03-09T00:00:00+00:00", ac1: 0.69, accuracy: 79, item_count: 100, bucket_item_count: 24, sample_item_count: 100, lookback_item_count: 76, sample_start: "2026-01-18T00:00:00+00:00", sample_end: "2026-03-08T18:00:00+00:00", sample_extended: true, agreements: 79, mismatches: 21 },
      { bucket_index: 2, label: "2026-03-09", start: "2026-03-09T00:00:00+00:00", end: "2026-03-16T00:00:00+00:00", ac1: 0.71, accuracy: 82, item_count: 100, bucket_item_count: 22, sample_item_count: 100, lookback_item_count: 78, sample_start: "2026-01-25T00:00:00+00:00", sample_end: "2026-03-15T18:00:00+00:00", sample_extended: true, agreements: 82, mismatches: 18 },
      { bucket_index: 3, label: "2026-03-16", start: "2026-03-16T00:00:00+00:00", end: "2026-03-23T00:00:00+00:00", ac1: 0.79, accuracy: 87, item_count: 100, bucket_item_count: 23, sample_item_count: 100, lookback_item_count: 77, sample_start: "2026-02-02T00:00:00+00:00", sample_end: "2026-03-22T18:00:00+00:00", sample_extended: true, agreements: 87, mismatches: 13 },
      { bucket_index: 4, label: "2026-03-23", start: "2026-03-23T00:00:00+00:00", end: "2026-03-30T00:00:00+00:00", ac1: 0.84, accuracy: 89, item_count: 100, bucket_item_count: 26, sample_item_count: 100, lookback_item_count: 74, sample_start: "2026-02-09T00:00:00+00:00", sample_end: "2026-03-29T18:00:00+00:00", sample_extended: true, agreements: 89, mismatches: 11 },
      { bucket_index: 5, label: "2026-03-30", start: "2026-03-30T00:00:00+00:00", end: "2026-04-06T00:00:00+00:00", ac1: 0.81, accuracy: 86, item_count: 100, bucket_item_count: 0, sample_item_count: 100, lookback_item_count: 100, sample_start: "2026-02-16T00:00:00+00:00", sample_end: "2026-03-29T18:00:00+00:00", sample_extended: true, agreements: 86, mismatches: 14 },
    ],
  },
  scores: [
    {
      score_id: "score-1",
      score_name: "Empathy",
      points: [
        { bucket_index: 0, label: "2026-02-23", start: "2026-02-23T00:00:00+00:00", end: "2026-03-02T00:00:00+00:00", ac1: 0.67, accuracy: 78, item_count: 60, bucket_item_count: 9, sample_item_count: 60, lookback_item_count: 51, sample_start: "2026-01-01T00:00:00+00:00", sample_end: "2026-03-01T18:00:00+00:00", sample_extended: true, sample_underfilled: true, agreements: 47, mismatches: 13 },
        { bucket_index: 1, label: "2026-03-02", start: "2026-03-02T00:00:00+00:00", end: "2026-03-09T00:00:00+00:00", ac1: 0.73, accuracy: 83, item_count: 70, bucket_item_count: 10, sample_item_count: 70, lookback_item_count: 60, sample_start: "2026-01-01T00:00:00+00:00", sample_end: "2026-03-08T18:00:00+00:00", sample_extended: true, sample_underfilled: true, agreements: 58, mismatches: 12 },
        { bucket_index: 2, label: "2026-03-09", start: "2026-03-09T00:00:00+00:00", end: "2026-03-16T00:00:00+00:00", ac1: 0.75, accuracy: 84, item_count: 81, bucket_item_count: 11, sample_item_count: 81, lookback_item_count: 70, sample_start: "2026-01-01T00:00:00+00:00", sample_end: "2026-03-15T18:00:00+00:00", sample_extended: true, sample_underfilled: true, agreements: 68, mismatches: 13 },
        { bucket_index: 3, label: "2026-03-16", start: "2026-03-16T00:00:00+00:00", end: "2026-03-23T00:00:00+00:00", ac1: 0.81, accuracy: 89, item_count: 91, bucket_item_count: 10, sample_item_count: 91, lookback_item_count: 81, sample_start: "2026-01-01T00:00:00+00:00", sample_end: "2026-03-22T18:00:00+00:00", sample_extended: true, sample_underfilled: true, agreements: 81, mismatches: 10 },
        { bucket_index: 4, label: "2026-03-23", start: "2026-03-23T00:00:00+00:00", end: "2026-03-30T00:00:00+00:00", ac1: 0.88, accuracy: 93, item_count: 100, bucket_item_count: 12, sample_item_count: 100, lookback_item_count: 88, sample_start: "2026-01-12T00:00:00+00:00", sample_end: "2026-03-29T18:00:00+00:00", sample_extended: true, agreements: 93, mismatches: 7 },
        { bucket_index: 5, label: "2026-03-30", start: "2026-03-30T00:00:00+00:00", end: "2026-04-06T00:00:00+00:00", ac1: 0.86, accuracy: 91, item_count: 100, bucket_item_count: 0, sample_item_count: 100, lookback_item_count: 100, sample_start: "2026-01-12T00:00:00+00:00", sample_end: "2026-03-29T18:00:00+00:00", sample_extended: true, agreements: 91, mismatches: 9 },
      ],
    },
    {
      score_id: "score-2",
      score_name: "Resolution",
      points: [
        { bucket_index: 0, label: "2026-02-23", start: "2026-02-23T00:00:00+00:00", end: "2026-03-02T00:00:00+00:00", ac1: 0.58, accuracy: 72, item_count: 11, agreements: 8, mismatches: 3 },
        { bucket_index: 1, label: "2026-03-02", start: "2026-03-02T00:00:00+00:00", end: "2026-03-09T00:00:00+00:00", ac1: 0.64, accuracy: 75, item_count: 14, agreements: 11, mismatches: 3 },
        { bucket_index: 2, label: "2026-03-09", start: "2026-03-09T00:00:00+00:00", end: "2026-03-16T00:00:00+00:00", ac1: 0.66, accuracy: 80, item_count: 11, agreements: 9, mismatches: 2 },
        { bucket_index: 3, label: "2026-03-16", start: "2026-03-16T00:00:00+00:00", end: "2026-03-23T00:00:00+00:00", ac1: 0.78, accuracy: 85, item_count: 13, agreements: 11, mismatches: 2 },
        { bucket_index: 4, label: "2026-03-23", start: "2026-03-23T00:00:00+00:00", end: "2026-03-30T00:00:00+00:00", ac1: 0.81, accuracy: 86, item_count: 14, agreements: 12, mismatches: 2 },
        { bucket_index: 5, label: "2026-03-30", start: "2026-03-30T00:00:00+00:00", end: "2026-04-06T00:00:00+00:00", ac1: null, accuracy: null, item_count: 0, agreements: 0, mismatches: 0 },
      ],
    },
  ],
  message: "Processed 2 score(s) across 6 complete bucket(s).",
};

export const AllScores: Story = {
  args: {
    name: "Feedback Alignment Timeline",
    type: "FeedbackAlignmentTimeline",
    position: 0,
    id: "feedback-alignment-timeline",
    config: {
      class: "FeedbackAlignmentTimeline",
      scorecard: "1438",
      bucket_type: "trailing_7d",
      bucket_count: 6,
    },
    output: baseOutput,
  },
};

export const SingleScore: Story = {
  args: {
    ...AllScores.args,
    config: {
      class: "FeedbackAlignmentTimeline",
      scorecard: "1438",
      score: "1438_1",
      bucket_type: "calendar_week",
      bucket_count: 6,
    },
    output: {
      ...baseOutput,
      mode: "single_score",
      overall: baseOutput.scores[0],
      scores: [baseOutput.scores[0]],
    },
  },
};

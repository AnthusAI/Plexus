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
          "Includes an introductory summary paragraph plus an always-visible Bucket Details list with per-bucket AC1/Accuracy gauges and raw agreement bars for the selected series.",
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
  overall: {
    score_id: "overall",
    score_name: "Overall",
    points: [
      { bucket_index: 0, label: "2026-02-23", start: "2026-02-23T00:00:00+00:00", end: "2026-03-02T00:00:00+00:00", ac1: 0.62, accuracy: 75, item_count: 20, agreements: 15, mismatches: 5 },
      { bucket_index: 1, label: "2026-03-02", start: "2026-03-02T00:00:00+00:00", end: "2026-03-09T00:00:00+00:00", ac1: 0.69, accuracy: 79, item_count: 24, agreements: 19, mismatches: 5 },
      { bucket_index: 2, label: "2026-03-09", start: "2026-03-09T00:00:00+00:00", end: "2026-03-16T00:00:00+00:00", ac1: 0.71, accuracy: 82, item_count: 22, agreements: 18, mismatches: 4 },
      { bucket_index: 3, label: "2026-03-16", start: "2026-03-16T00:00:00+00:00", end: "2026-03-23T00:00:00+00:00", ac1: 0.79, accuracy: 87, item_count: 23, agreements: 20, mismatches: 3 },
      { bucket_index: 4, label: "2026-03-23", start: "2026-03-23T00:00:00+00:00", end: "2026-03-30T00:00:00+00:00", ac1: 0.84, accuracy: 89, item_count: 26, agreements: 23, mismatches: 3 },
      { bucket_index: 5, label: "2026-03-30", start: "2026-03-30T00:00:00+00:00", end: "2026-04-06T00:00:00+00:00", ac1: null, accuracy: null, item_count: 0, agreements: 0, mismatches: 0 },
    ],
  },
  scores: [
    {
      score_id: "score-1",
      score_name: "Empathy",
      points: [
        { bucket_index: 0, label: "2026-02-23", start: "2026-02-23T00:00:00+00:00", end: "2026-03-02T00:00:00+00:00", ac1: 0.67, accuracy: 78, item_count: 9, agreements: 7, mismatches: 2 },
        { bucket_index: 1, label: "2026-03-02", start: "2026-03-02T00:00:00+00:00", end: "2026-03-09T00:00:00+00:00", ac1: 0.73, accuracy: 83, item_count: 10, agreements: 8, mismatches: 2 },
        { bucket_index: 2, label: "2026-03-09", start: "2026-03-09T00:00:00+00:00", end: "2026-03-16T00:00:00+00:00", ac1: 0.75, accuracy: 84, item_count: 11, agreements: 9, mismatches: 2 },
        { bucket_index: 3, label: "2026-03-16", start: "2026-03-16T00:00:00+00:00", end: "2026-03-23T00:00:00+00:00", ac1: 0.81, accuracy: 89, item_count: 10, agreements: 9, mismatches: 1 },
        { bucket_index: 4, label: "2026-03-23", start: "2026-03-23T00:00:00+00:00", end: "2026-03-30T00:00:00+00:00", ac1: 0.88, accuracy: 93, item_count: 12, agreements: 11, mismatches: 1 },
        { bucket_index: 5, label: "2026-03-30", start: "2026-03-30T00:00:00+00:00", end: "2026-04-06T00:00:00+00:00", ac1: null, accuracy: null, item_count: 0, agreements: 0, mismatches: 0 },
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

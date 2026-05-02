export type ReportDoc = {
  slug: string;
  title: string;
  type?: string;
  category: "Feedback quality" | "Trends" | "Operational" | "Analysis" | "Related checks";
  badge: string;
  summary: string;
  answers: string[];
  useWhen: string[];
  avoidWhen: string[];
  cli?: string;
  tactus?: string;
  config?: string;
  interpretation: string[];
  sampleOutput?: Record<string, unknown>;
  relatedCheck?: boolean;
};

const dateRange = {
  start: "2026-03-01T00:00:00Z",
  end: "2026-03-31T23:59:59Z",
};

const topic = {
  label: "Schedule discussed without dosage",
  keywords: ["schedule", "dosage", "medication review"],
  memory_weight: 0.82,
  memory_tier: "hot",
  lifecycle_tier: "trending",
  member_count: 18,
  days_inactive: 2,
  cause: "Reviewers are correcting calls where the agent confirmed timing but not the numeric dose.",
  exemplars: [
    {
      text: "The agent reviewed when the medication is taken but did not verify the dosage amount.",
      item_id: "example-item-001",
      initial_answer_value: "Yes",
      final_answer_value: "No",
      score_explanation: "The model treated schedule confirmation as sufficient.",
    },
  ],
};

export const reportDocs: ReportDoc[] = [
  {
    slug: "feedback-alignment",
    title: "FeedbackAlignment",
    type: "FeedbackAlignment",
    category: "Feedback quality",
    badge: "Analytics",
    summary: "Measures agreement between AI score results and human feedback using AC1, accuracy, class distribution, and confusion matrices.",
    answers: ["How aligned is this score with human feedback?", "Which labels are being confused?", "Which scores need attention first?"],
    useWhen: ["Starting score optimization.", "Comparing scorecard-level alignment across scores.", "Checking whether recent rubric or prompt changes improved feedback agreement."],
    avoidWhen: ["You need individual contradiction explanations; use FeedbackContradictions.", "You only need marketing-friendly acceptance numbers; use AcceptanceRate."],
    cli: `plexus feedback report alignment \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --days 30 \\
  --format json`,
    config: `class: FeedbackAlignment
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"
days: 30`,
    interpretation: ["High AC1 means the score and reviewers agree beyond chance.", "Use the confusion matrix to choose whether to focus on false positives or false negatives.", "Low item count should be treated as weak evidence, even if the gauge looks strong."],
    sampleOutput: {
      overall_ac1: 0.74,
      total_items: 120,
      total_agreements: 96,
      total_mismatches: 24,
      accuracy: 80,
      date_range: dateRange,
      scores: [
        {
          id: "score-dosage",
          score_name: "Medication Review: Dosage",
          ac1: 0.74,
          item_count: 120,
          mismatches: 24,
          agreements: 96,
          accuracy: 80,
          label_distribution: { Yes: 70, No: 50 },
          confusion_matrix: {
            labels: ["Yes", "No"],
            matrix: [
              { actualClassLabel: "Yes", predictedClassCounts: { Yes: 62, No: 8 } },
              { actualClassLabel: "No", predictedClassCounts: { Yes: 16, No: 34 } },
            ],
          },
        },
      ],
      label_distribution: { Yes: 70, No: 50 },
    },
  },
  {
    slug: "feedback-contradictions",
    title: "FeedbackContradictions",
    type: "FeedbackContradictions",
    category: "Feedback quality",
    badge: "Curation",
    summary: "Finds feedback edits that appear to contradict the current rubric, grouping likely invalid feedback into reviewable topics.",
    answers: ["Which feedback items may be invalid under the current rubric?", "What policy themes explain the contradictions?", "Which examples should be reviewed before feedback curation?"],
    useWhen: ["After rubric changes.", "Before building feedback datasets.", "Before optimizing against feedback that may contain stale policy labels."],
    avoidWhen: ["You want aggregate alignment only; use FeedbackAlignment.", "You need a final invalidation action; this report proposes candidates but does not replace review."],
    cli: `plexus feedback report contradictions \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --days 90 \\
  --include-rubric-memory \\
  --format json`,
    config: `class: FeedbackContradictions
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"
days: 90
include_rubric_memory: true
max_feedback_items: 400`,
    interpretation: ["Topics are review queues, not automatic invalidation commands.", "High-confidence topics with reviewer comments are the strongest curation candidates.", "Rubric-memory citations help explain whether a correction reflects current policy or stale historical guidance."],
    sampleOutput: {
      mode: "contradictions",
      score_name: "Medication Review: Dosage",
      total_items_analyzed: 64,
      items_vetted: 64,
      contradictions_found: 9,
      selected_items_count: 9,
      topics: [
        {
          label: "Customer acknowledgment required by stale feedback",
          summary: "Feedback expects separate customer acknowledgment even though the current rubric treats individual confirmation as a separate score.",
          guideline_quote: "Do not require separate dosage acknowledgment when another score handles individual confirmation.",
          count: 9,
          exemplars: [
            {
              feedback_item_id: "feedback-001",
              item_id: "item-001",
              initial_value: "Yes",
              final_value: "No",
              edit_comment: "Customer did not repeat back the dosage.",
              reason: "Current rubric does not require repeat-back for this score.",
              guideline_quote: "Individual confirmation is handled by a separate score.",
              is_invalid: false,
              confidence: "high",
              voting: [
                { model: "gpt", result: true, reason: "Contradicts current rubric." },
                { model: "haiku", result: true, reason: "Reviewer applied an older policy." },
              ],
            },
          ],
        },
      ],
    },
  },
  {
    slug: "recent-feedback",
    title: "RecentFeedback",
    type: "RecentFeedback",
    category: "Feedback quality",
    badge: "Review",
    summary: "Shows the most recent feedback items for a score or scorecard, including reviewer edits and item identifiers.",
    answers: ["What are reviewers correcting right now?", "Which recent examples should I inspect?", "Is new feedback arriving for this score?"],
    useWhen: ["Preparing for a score review.", "Spot-checking recent rubric changes.", "Finding examples to discuss with SMEs."],
    avoidWhen: ["You need agreement statistics; use FeedbackAlignment.", "You need contradiction voting; use FeedbackContradictions."],
    cli: `plexus feedback report recent \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --days 14 \\
  --max-feedback-items 50`,
    config: `class: RecentFeedback
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"
days: 14
max_feedback_items: 50`,
    interpretation: ["Read newest rows first when looking for active rubric drift.", "Repeated edit comments are often better optimization clues than isolated corrections."],
    sampleOutput: {
      report_type: "recent_feedback",
      block_title: "Recent Feedback",
      block_description: "Newest feedback edits for the selected score.",
      scorecard_name: "Customer Service QA",
      score_name: "Medication Review: Dosage",
      date_range: dateRange,
      summary: {
        total_feedback_items: 3,
        corrected_feedback_items: 2,
        agreed_feedback_items: 1,
        invalid_feedback_items: 0,
        distinct_items_count: 3,
        distinct_score_count: 1,
      },
      items: [
        {
          feedback_item_id: "feedback-003",
          item_id: "item-003",
          score_id: "score-dosage",
          score_name: "Medication Review: Dosage",
          item_external_id: "CALL-003",
          initial_value: "Yes",
          final_value: "No",
          corrected: true,
          is_invalid: false,
          edit_comment: "Dosage was implied by schedule, not verified.",
          edited_at: "2026-03-30T15:10:00Z",
        },
      ],
    },
  },
  {
    slug: "feedback-alignment-timeline",
    title: "FeedbackAlignmentTimeline",
    type: "FeedbackAlignmentTimeline",
    category: "Trends",
    badge: "Trend",
    summary: "Plots alignment metrics across complete historical buckets so teams can see whether agreement is improving or drifting.",
    answers: ["Is alignment improving over time?", "Did a release or rubric change move AC1?", "Which completed periods had no feedback?"],
    useWhen: ["Reviewing week-over-week score health.", "Checking post-release drift.", "Separating recent trend from long-window averages."],
    avoidWhen: ["You only need the latest aggregate; use FeedbackAlignment.", "You need feedback volume only; use FeedbackVolumeTimeline."],
    cli: `plexus feedback report timeline \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --bucket-type calendar_week \\
  --bucket-count 6 \\
  --show-bucket-details`,
    config: `class: FeedbackAlignmentTimeline
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"
bucket_type: calendar_week
bucket_count: 6
show_bucket_details: true`,
    interpretation: ["Only complete buckets are shown, so partial current periods do not distort the trend.", "Falling AC1 with stable feedback volume usually means policy or score behavior drift."],
    sampleOutput: {
      mode: "single_score",
      block_title: "Feedback Alignment Timeline",
      block_description: "Alignment metrics over complete historical buckets",
      bucket_policy: { bucket_type: "calendar_week", bucket_count: 4, timezone: "UTC", week_start: "monday", complete_only: true },
      overall: {
        score_id: "score-dosage",
        score_name: "Medication Review: Dosage",
        points: [
          { bucket_index: 0, label: "Mar 2", start: "2026-03-02T00:00:00Z", end: "2026-03-09T00:00:00Z", ac1: 0.62, accuracy: 75, item_count: 20, agreements: 15, mismatches: 5 },
          { bucket_index: 1, label: "Mar 9", start: "2026-03-09T00:00:00Z", end: "2026-03-16T00:00:00Z", ac1: 0.71, accuracy: 82, item_count: 22, agreements: 18, mismatches: 4 },
          { bucket_index: 2, label: "Mar 16", start: "2026-03-16T00:00:00Z", end: "2026-03-23T00:00:00Z", ac1: 0.79, accuracy: 87, item_count: 23, agreements: 20, mismatches: 3 },
          { bucket_index: 3, label: "Mar 23", start: "2026-03-23T00:00:00Z", end: "2026-03-30T00:00:00Z", ac1: 0.84, accuracy: 89, item_count: 26, agreements: 23, mismatches: 3 },
        ],
      },
      scores: [],
      message: "Processed 1 score across 4 complete buckets.",
    },
  },
  {
    slug: "feedback-volume-timeline",
    title: "FeedbackVolumeTimeline",
    type: "FeedbackVolumeTimeline",
    category: "Trends",
    badge: "Trend",
    summary: "Shows how much feedback arrived in each completed time bucket.",
    answers: ["Is feedback volume stable?", "Were there enough recent examples to trust an alignment change?", "Which periods need more review coverage?"],
    useWhen: ["Interpreting timeline metrics.", "Checking whether low confidence comes from low volume.", "Monitoring reviewer throughput."],
    avoidWhen: ["You need agreement quality; use FeedbackAlignmentTimeline.", "You need item-level rows; use RecentFeedback."],
    cli: `plexus feedback report volume \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --bucket-type trailing_7d \\
  --bucket-count 8`,
    config: `class: FeedbackVolumeTimeline
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"
bucket_type: trailing_7d
bucket_count: 8`,
    interpretation: ["A drop in feedback volume can make alignment gauges unstable.", "Use this with FeedbackAlignmentTimeline before treating a trend as real."],
    sampleOutput: {
      report_type: "feedback_volume_timeline",
      block_title: "Feedback Volume Timeline",
      block_description: "Feedback volume over complete historical buckets",
      scorecard_name: "Customer Service QA",
      score_name: "Medication Review: Dosage",
      bucket_policy: { bucket_type: "trailing_7d", bucket_count: 4, timezone: "UTC", complete_only: true },
      show_bucket_details: true,
      summary: {
        feedback_items_total: 92,
        feedback_items_valid: 88,
        feedback_items_unchanged: 77,
        feedback_items_changed: 11,
        feedback_items_invalid_or_unclassified: 4,
      },
      points: [
        { bucket_index: 0, label: "Mar 2", start: "2026-03-02T00:00:00Z", end: "2026-03-09T00:00:00Z", feedback_items_total: 20, feedback_items_valid: 19, feedback_items_unchanged: 14, feedback_items_changed: 5, feedback_items_invalid_or_unclassified: 1 },
        { bucket_index: 1, label: "Mar 9", start: "2026-03-09T00:00:00Z", end: "2026-03-16T00:00:00Z", feedback_items_total: 22, feedback_items_valid: 22, feedback_items_unchanged: 18, feedback_items_changed: 4, feedback_items_invalid_or_unclassified: 0 },
        { bucket_index: 2, label: "Mar 16", start: "2026-03-16T00:00:00Z", end: "2026-03-23T00:00:00Z", feedback_items_total: 23, feedback_items_valid: 21, feedback_items_unchanged: 18, feedback_items_changed: 3, feedback_items_invalid_or_unclassified: 2 },
        { bucket_index: 3, label: "Mar 23", start: "2026-03-23T00:00:00Z", end: "2026-03-30T00:00:00Z", feedback_items_total: 27, feedback_items_valid: 26, feedback_items_unchanged: 23, feedback_items_changed: 3, feedback_items_invalid_or_unclassified: 1 },
      ],
    },
  },
  {
    slug: "score-champion-version-timeline",
    title: "ScoreChampionVersionTimeline",
    type: "ScoreChampionVersionTimeline",
    category: "Trends",
    badge: "Optimizer",
    summary: "Plots score champion version changes during a requested time window with feedback and regression evaluation metrics.",
    answers: ["Which champion versions shipped during this window?", "Did champion feedback and regression metrics improve?", "What changed between the prior champion and the latest champion?"],
    useWhen: ["Reviewing optimizer impact after score improvement work.", "Explaining production champion changes over time.", "Auditing manually promoted score versions."],
    avoidWhen: ["You need every optimizer candidate; use procedure optimizer views.", "The score predates championHistory metadata and has no recorded transitions."],
    cli: `plexus feedback report score-champion-version-timeline \\
  --scorecard "Customer Service QA" \\
  --days 30

# Add --include-unchanged to include initial champion entries with no previous champion.`,
    tactus: `return plexus.report.score_champion_version_timeline{
  scorecard = "Customer Service QA",
  days = 30,
  sync = true
}`,
    config: `class: ScoreChampionVersionTimeline
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"
days: 30
include_unchanged: false`,
    interpretation: ["By default, initial champion entries with no previous champion are omitted because they are not changes; set include_unchanged to true to show them.", "Only versions with championHistory enteredAt values inside the requested window are included.", "The displayed date range is narrowed to one day before the earliest champion activity when the request window is much broader than the activity.", "Missing feedback or regression evaluations are shown as unavailable instead of suppressing the champion point.", "Procedure, evaluation, score-result, and cost totals summarize optimizer work during the window.", "SME agenda and worksheet content comes from the most recent optimizer procedure for each score.", "Diffs compare the previous champion before the first in-window transition to the latest in-window champion."],
    sampleOutput: {
      report_type: "score_champion_version_timeline",
      block_title: "Score Champion Version Timeline",
      block_description: "Champion version changes and associated evaluation metrics",
      scope: "single_score",
      scorecard_name: "Customer Service QA",
      requested_date_range: dateRange,
      date_range: {
        start: "2026-03-11T14:20:00Z",
        end: dateRange.end,
        normalized_to_activity: true,
      },
      include_unchanged: false,
      summary: {
        scores_analyzed: 1,
        scores_with_champion_changes: 1,
        champion_change_count: 2,
        procedure_count: 1,
        evaluation_count: 4,
        score_result_count: 600,
        optimization_cost: { overall: 2.42, inference: 0.38, evaluation: 2.04 },
        associated_evaluation_cost: 0.64,
        evaluations_scanned: 4,
      },
      scores: [
        {
          score_id: "score-dosage",
          score_name: "Medication Review: Dosage",
          optimization_summary: {
            procedure_count: 1,
            evaluation_count: 4,
            score_result_count: 600,
            optimization_cost: { overall: 2.42, inference: 0.38, evaluation: 2.04 },
            associated_evaluation_cost: 0.64,
          },
          points: [
            {
              point_index: 0,
              label: "2026-03-12",
              entered_at: "2026-03-12T14:20:00Z",
              version_id: "version-101",
              previous_champion_version_id: "version-100",
              feedback_evaluation_id: "eval-feedback-101",
              feedback_metrics: { alignment: 0.71, accuracy: 82, processed_items: 100, total_items: 100 },
              regression_evaluation_id: "eval-regression-101",
              regression_metrics: { alignment: 0.68, accuracy: 79, processed_items: 200, total_items: 200 },
            },
            {
              point_index: 1,
              label: "2026-03-26",
              entered_at: "2026-03-26T09:10:00Z",
              version_id: "version-102",
              previous_champion_version_id: "version-101",
              feedback_evaluation_id: "eval-feedback-102",
              feedback_metrics: { alignment: 0.78, accuracy: 87 },
              regression_evaluation_id: "eval-regression-102",
              regression_metrics: { alignment: 0.72, accuracy: 81 },
            },
          ],
          sme: {
            procedure_id: "procedure-optimizer-102",
            procedure_status: "COMPLETED",
            procedure_updated_at: "2026-03-26T10:30:00Z",
            available: true,
            agenda: "Review dosage exception wording with SME.",
            worksheet: "Confirm whether ambiguous dosage mentions should be excluded.",
            generated_at: "2026-03-26T10:35:00Z",
          },
          diff: {
            left_version_id: "version-100",
            right_version_id: "version-102",
            configuration_left: "name: old",
            configuration_right: "name: new",
            configuration_diff: "--- version-100/configuration\n+++ version-102/configuration\n@@ -1 +1 @@\n-name: old\n+name: new",
            guidelines_left: "Old rubric",
            guidelines_right: "New rubric",
            guidelines_diff: "--- version-100/guidelines\n+++ version-102/guidelines\n@@ -1 +1 @@\n-Old rubric\n+New rubric",
          },
        },
      ],
    },
  },
  {
    slug: "acceptance-rate-timeline",
    title: "AcceptanceRateTimeline",
    type: "AcceptanceRateTimeline",
    category: "Trends",
    badge: "Trend",
    summary: "Tracks score-result acceptance rate over time for stakeholder-friendly monitoring.",
    answers: ["Are reviewers accepting more AI decisions over time?", "Did acceptance improve after a score release?", "Which periods had weak acceptance?"],
    useWhen: ["Reporting product progress.", "Monitoring high-level reviewer trust.", "Comparing before/after release windows."],
    avoidWhen: ["You need confusion matrix detail; use FeedbackAlignment.", "You need per-topic failure modes; use FeedbackContradictions."],
    cli: `plexus feedback report acceptance-rate-timeline \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --bucket-type calendar_week \\
  --bucket-count 6`,
    config: `class: AcceptanceRateTimeline
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"
bucket_type: calendar_week
bucket_count: 6`,
    interpretation: ["This is good for trend communication, but it does not explain which class is wrong.", "Compare with feedback volume before claiming a meaningful improvement."],
    sampleOutput: {
      report_type: "acceptance_rate_timeline",
      block_title: "Acceptance Rate Timeline",
      block_description: "Score-result acceptance over complete historical buckets",
      scorecard_name: "Customer Service QA",
      score_name: "Medication Review: Dosage",
      bucket_policy: { bucket_type: "calendar_week", bucket_count: 4 },
      show_bucket_details: true,
      summary: { total_score_results: 400, accepted_score_results: 344, corrected_score_results: 56, score_result_acceptance_rate: 0.86, feedback_items_total: 88, feedback_items_valid: 84, feedback_items_changed: 56, score_results_with_feedback: 400 },
      points: [
        { bucket_index: 0, label: "Mar 2", start: "2026-03-02T00:00:00Z", end: "2026-03-09T00:00:00Z", total_score_results: 100, accepted_score_results: 82, corrected_score_results: 18, score_result_acceptance_rate: 0.82, feedback_items_total: 20, feedback_items_valid: 19, feedback_items_changed: 18, score_results_with_feedback: 100 },
        { bucket_index: 1, label: "Mar 9", start: "2026-03-09T00:00:00Z", end: "2026-03-16T00:00:00Z", total_score_results: 95, accepted_score_results: 81, corrected_score_results: 14, score_result_acceptance_rate: 0.85, feedback_items_total: 22, feedback_items_valid: 22, feedback_items_changed: 14, score_results_with_feedback: 95 },
        { bucket_index: 2, label: "Mar 16", start: "2026-03-16T00:00:00Z", end: "2026-03-23T00:00:00Z", total_score_results: 105, accepted_score_results: 92, corrected_score_results: 13, score_result_acceptance_rate: 0.876, feedback_items_total: 23, feedback_items_valid: 21, feedback_items_changed: 13, score_results_with_feedback: 105 },
        { bucket_index: 3, label: "Mar 23", start: "2026-03-23T00:00:00Z", end: "2026-03-30T00:00:00Z", total_score_results: 100, accepted_score_results: 89, corrected_score_results: 11, score_result_acceptance_rate: 0.89, feedback_items_total: 23, feedback_items_valid: 22, feedback_items_changed: 11, score_results_with_feedback: 100 },
      ],
    },
  },
  {
    slug: "acceptance-rate",
    title: "AcceptanceRate",
    type: "AcceptanceRate",
    category: "Operational",
    badge: "Marketing",
    summary: "Measures the share of score results, and optionally items, accepted by reviewers without correction.",
    answers: ["How often do reviewers accept AI decisions?", "Can we show a simple positive trust metric?", "Which recent items were fully accepted or corrected?"],
    useWhen: ["Stakeholder updates.", "High-level adoption reporting.", "Complementing technical alignment metrics."],
    avoidWhen: ["You need chance-corrected agreement; use FeedbackAlignment.", "You need class-level failure modes."],
    cli: `plexus feedback report acceptance-rate \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --days 30 \\
  --include-item-acceptance-rate`,
    config: `class: AcceptanceRate
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"
days: 30
include_item_acceptance_rate: true
max_items: 25`,
    interpretation: ["Acceptance rate is intuitive, but less diagnostic than AC1.", "Use item acceptance when a human-friendly story matters more than score-result granularity."],
    sampleOutput: {
      report_type: "acceptance_rate",
      block_title: "Acceptance Rate",
      block_description: "Reviewer acceptance for selected score results.",
      include_item_acceptance_rate: true,
      scorecard_name: "Customer Service QA",
      score_name: "Medication Review: Dosage",
      date_range: dateRange,
      summary: {
        total_items: 80,
        accepted_items: 68,
        corrected_items: 12,
        item_acceptance_rate: 0.85,
        total_score_results: 120,
        accepted_score_results: 103,
        corrected_score_results: 17,
        score_result_acceptance_rate: 0.858,
        feedback_items_total: 80,
        feedback_items_valid: 78,
        feedback_items_changed: 17,
        score_results_with_feedback: 120,
      },
      items: [
        { item_id: "item-001", item_external_id: "CALL-001", item_accepted: true, total_score_results: 2, accepted_score_results: 2, corrected_score_results: 0, score_result_acceptance_rate: 1 },
      ],
    },
  },
  {
    slug: "correction-rate",
    title: "CorrectionRate",
    type: "CorrectionRate",
    category: "Operational",
    badge: "Operations",
    summary: "Shows how often feedback changes AI answers, which is the inverse operational view of acceptance.",
    answers: ["How many reviewed results were corrected?", "Which recent items required changes?", "How large is the feedback correction workload?"],
    useWhen: ["Operational workload reviews.", "Comparing correction pressure between scores.", "Finding recent corrected examples."],
    avoidWhen: ["You need a positive stakeholder metric; use AcceptanceRate.", "You need chance-corrected quality; use FeedbackAlignment."],
    cli: `plexus feedback report correction-rate \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --days 30`,
    config: `class: CorrectionRate
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"
days: 30
max_items: 25`,
    interpretation: ["High correction rate means reviewers often disagree with AI outputs.", "Pair this with contradiction analysis before assuming every correction is valid training signal."],
    sampleOutput: {
      report_type: "correction_rate",
      block_title: "Correction Rate",
      block_description: "Feedback correction rate for selected score results.",
      scorecard_name: "Customer Service QA",
      score_name: "Medication Review: Dosage",
      date_range: dateRange,
      summary: { total_items: 80, total_score_results: 120, corrected_score_results: 17, uncorrected_score_results: 103, corpus_correction_rate: 0.1417 },
      items: [
        { item_id: "item-001", total_score_results: 2, corrected_score_results: 1, uncorrected_score_results: 1, correction_rate: 0.5 },
      ],
    },
  },
  {
    slug: "cost-analysis",
    title: "CostAnalysis",
    type: "CostAnalysis",
    category: "Operational",
    badge: "Cost",
    summary: "Summarizes score-result cost and call-count distribution across scorecards, scores, or windows.",
    answers: ["Which scores are expensive?", "What is average cost per item?", "Where should we optimize model or prompt cost?"],
    useWhen: ["Cost review.", "Model migration planning.", "Investigating unusually expensive scoring runs."],
    avoidWhen: ["You need accuracy or alignment quality.", "You need per-feedback curation."],
    cli: `plexus report run --config "Cost Review" days=7`,
    config: `class: CostAnalysis
scorecard: "Customer Service QA"
days: 7
group_by: score`,
    interpretation: ["Look for high average cost per item before optimizing total cost.", "A score with high total cost may simply have high volume."],
    sampleOutput: {
      block_description: "Cost over the last seven days.",
      scorecardName: "Customer Service QA",
      summary: { average_cost: "0.0142", count: 2400, total_cost: "34.0800", average_calls: "3.2" },
      itemAnalysis: { count: 800, total_cost: 34.08, average_cost: 0.0426, average_calls: 3.2 },
      groups: [
        { group: { scoreName: "Medication Review: Dosage" }, average_cost: "0.015", count: 800, total_cost: "12.000", min_cost: 0.004, q1_cost: 0.01, median_cost: 0.014, q3_cost: 0.019, max_cost: 0.04 },
        { group: { scoreName: "Agent Misrepresentation" }, average_cost: "0.011", count: 600, total_cost: "6.600", min_cost: 0.003, q1_cost: 0.008, median_cost: 0.01, q3_cost: 0.014, max_cost: 0.03 },
      ],
    },
  },
  {
    slug: "topic-analysis",
    title: "TopicAnalysis",
    type: "TopicAnalysis",
    category: "Analysis",
    badge: "NLP",
    summary: "Clusters text into topic groups using the report topic-analysis pipeline.",
    answers: ["What topics appear in this text corpus?", "Which examples represent each topic?", "What keywords describe each cluster?"],
    useWhen: ["Exploring unlabeled transcript text.", "Finding themes in free-form comments.", "Creating a first-pass taxonomy."],
    avoidWhen: ["You need feedback-vs-rubric contradictions.", "You need deterministic score metrics."],
    cli: `plexus report run --config "Topic Analysis" source=customer-calls sample_size=1000`,
    config: `class: TopicAnalysis
data:
  source: "customer-calls"
  content_column: "text"
llm_extraction:
  method: "chunk"
bertopic_analysis:
  min_topic_size: 10`,
    interpretation: ["Topic names are descriptive labels, not final policy conclusions.", "Review examples before acting on a cluster."],
    sampleOutput: {
      summary: "Topic analysis completed successfully.",
      topics: [
        { id: 0, name: "billing questions", count: 42, representation: "billing charges statement", words: [{ word: "billing", weight: 0.14 }], examples: ["Customer asked about statement charges."] },
      ],
      attached_files: [],
      errors: [],
    },
  },
  {
    slug: "explanation-analysis",
    title: "ExplanationAnalysis",
    type: "ExplanationAnalysis",
    category: "Analysis",
    badge: "NLP",
    summary: "Clusters score-result explanations to reveal recurring model reasoning patterns.",
    answers: ["What reasons does the model give most often?", "Which reasoning patterns correlate with misses?", "Where are explanations repetitive or vague?"],
    useWhen: ["Auditing model reasoning.", "Preparing optimizer context.", "Finding repeated explanation themes."],
    avoidWhen: ["You need transcript topics instead of score explanations.", "You need direct feedback agreement metrics."],
    cli: `plexus report run --config "Explanation Analysis" days=30`,
    config: `class: ExplanationAnalysis
scorecard: "Customer Service QA"
days: 30
min_topic_size: 5`,
    interpretation: ["Reasoning topics can reveal prompt ambiguity even when labels look acceptable.", "Use exemplars to confirm the model is not rationalizing wrong outputs."],
    sampleOutput: {
      type: "explanation_analysis",
      summary: "Clustered explanations for selected scorecard.",
      scorecard_name: "Customer Service QA",
      date_range: dateRange,
      total_explanations_retained: 120,
      scores: [{ score_id: "score-dosage", score_name: "Medication Review: Dosage", items_processed: 120, topics: [topic] }],
    },
  },
  {
    slug: "vector-topic-memory",
    title: "VectorTopicMemory",
    type: "VectorTopicMemory",
    category: "Analysis",
    badge: "Memory",
    summary: "Rebuilds a topic-memory view using vector clustering so recurring topics can be tracked across runs.",
    answers: ["Which topics are recurring?", "Which topics are new or trending?", "What has persisted in memory?"],
    useWhen: ["Maintaining topic memory for RCA or optimization.", "Looking for recurring issue clusters.", "Comparing short- and long-term themes."],
    avoidWhen: ["You only need a one-off topic model.", "You need simple aggregate metrics."],
    cli: `plexus report run --config "Vector Topic Memory" days=90`,
    config: `class: VectorTopicMemory
scorecard: "Customer Service QA"
days: 90
memory_scope: "scorecard"`,
    interpretation: ["Hot topics deserve attention first.", "New and trending badges indicate topics that recently changed, not necessarily the largest clusters."],
    sampleOutput: {
      type: "vector_topic_memory",
      status: "success",
      cluster_version: "2026-03",
      items_processed: 180,
      cache_hit_rate: 0.76,
      scores: [{ score_id: "score-dosage", score_name: "Medication Review: Dosage", items_processed: 180, topics: [topic] }],
    },
  },
  {
    slug: "action-items",
    title: "ActionItems",
    type: "ActionItems",
    category: "Analysis",
    badge: "Workflow",
    summary: "Turns alignment and topic-memory findings into prioritized score-improvement action items.",
    answers: ["What should the team work on next?", "Which score/topic combination needs attention?", "Which examples support the action item?"],
    useWhen: ["Preparing an optimization agenda.", "Reviewing stakeholder action lists.", "Triaging low-AC1 recurring topics."],
    avoidWhen: ["You need raw metrics only.", "You have not generated prerequisite alignment or topic-memory context."],
    cli: `plexus report action-items --report <report-id>`,
    config: `class: ActionItems
ac1_threshold: 0.70
recency_days: 30`,
    interpretation: ["Treat each card as a triage recommendation.", "Use exemplars and copied JSON when handing work to an agent or engineer."],
    sampleOutput: {
      total_count: 1,
      generated_at: "2026-03-31T00:00:00Z",
      thresholds: { ac1_threshold: 0.7, recency_days: 30 },
      action_items: [
        {
          scorecard_name: "Customer Service QA",
          score_name: "Medication Review: Dosage",
          score_ac1: 0.62,
          score_mismatches: 18,
          topic_label: "Schedule discussed without dosage",
          cause: "The score treats schedule language as dosage verification.",
          keywords: ["schedule", "dosage"],
          member_count: 18,
          days_inactive: 2,
          lifecycle_tier: "trending",
          is_new: false,
          is_trending: true,
          exemplars: [{ text: "Agent confirmed timing but not dosage.", initial_answer_value: "Yes", final_answer_value: "No" }],
        },
      ],
    },
  },
  {
    slug: "score-info",
    title: "ScoreInfo",
    type: "ScoreInfo",
    category: "Analysis",
    badge: "Context",
    summary: "Displays compact score metadata inside a report.",
    answers: ["Which score is this report about?", "What is the score description?", "When was this score last updated?"],
    useWhen: ["Adding context to composite reports.", "Providing a lightweight header for score-specific report output."],
    avoidWhen: ["You need metrics or feedback analysis.", "The report already has enough score context."],
    cli: `plexus report run --config "Score Overview"`,
    config: `class: ScoreInfo
scorecard: "Customer Service QA"
score: "Medication Review: Dosage"`,
    interpretation: ["ScoreInfo is context, not analysis.", "Use it to orient readers before deeper report blocks."],
    sampleOutput: {
      name: "Medication Review: Dosage",
      description: "Checks whether the agent verified dosage information for current medications.",
      accuracy: 0.84,
      updatedAt: "2026-03-28T14:30:00Z",
    },
  },
  {
    slug: "score-rubric-consistency",
    title: "Score/Rubric Consistency Check",
    category: "Related checks",
    badge: "Preflight",
    summary: "Checks whether a ScoreVersion's code and prompt appear consistent with that same version's rubric.",
    answers: ["Does this score version implement its rubric?", "Should I investigate a code/rubric mismatch before evaluation?", "Is an item useful as spot-check context?"],
    useWhen: ["Before promotion.", "Before a feedback evaluation.", "When evaluation results suggest the prompt and rubric may disagree."],
    avoidWhen: ["You need feedback item curation; use FeedbackContradictions.", "You need a full evaluation; this is only a preflight check."],
    cli: `plexus score contradictions \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --version abc123-version-uuid \\
  --format json`,
    config: `# This is not a ReportBlock. It is a score command.
plexus score contradictions \\
  --scorecard "Customer Service QA" \\
  --score "Medication Review: Dosage" \\
  --version abc123-version-uuid`,
    interpretation: ["`consistent` means no obvious mismatch was found; it is not a replacement for evaluation.", "`potential_conflict` should block promotion until a human reviews the finding.", "`inconclusive` usually means the rubric or code was missing or too ambiguous."],
    relatedCheck: true,
  },
];

export const reportDocBySlug = Object.fromEntries(reportDocs.map((doc) => [doc.slug, doc]));

export const reportDocCategories = [
  "Feedback quality",
  "Trends",
  "Operational",
  "Analysis",
  "Related checks",
] as const;

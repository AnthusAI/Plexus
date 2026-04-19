# Feedback Alignment Workflow

This document is for optimizer agents and score editors who are improving a score
against human feedback. Follow this process in order. The workflow is baseline-first
and local-first: measure the current behavior, investigate the right segment, edit
locally, and re-evaluate on the same baseline before considering any release step.

## Terminology Policy

Do not use legacy positive/negative error shorthand or any two-letter abbreviation
that depends on an implied "positive class".

Use:

- `P"No"->A"Yes"` for cases where the model predicted `"No"` but the actual label was `"Yes"`
- `P"Yes"->A"No"` for cases where the model predicted `"Yes"` but the actual label was `"No"`

Use the full prose form when clarity matters more than compactness.

## Start Here

Open the relevant docs before editing:

- `score-concepts`
- `score-yaml-format`
- `score-yaml-langgraph` or `score-yaml-tactusscore`
- `optimizer-cookbook`

Then run the required planning step with `think` so the baseline-first workflow is
explicit in the session.

## Ground Rules

- Pull the current champion YAML locally before editing.
- Do not push a new score version during feedback-alignment iteration.
- Do not promote champion during feedback-alignment iteration.
- Keep evaluations local by using the YAML-backed score configuration.
- Compare against the same baseline dataset or associated dataset whenever possible.

## Phase 1: Pull the Current Score and Establish Context

Use `plexus_score_pull` to get the current champion YAML and guidelines locally.

Example:

```text
plexus_score_pull(
    scorecard_identifier="Quality Assurance v1.0",
    score_identifier="Compliance Check"
)
```

Read the current score carefully before proposing changes:

- What score class is it?
- Is the score already decomposed?
- Does it mix applicability with the core Yes/No decision?
- Does it already use input shaping or processors?
- Is the issue likely prompt-level, structural, or transcript-format related?

## Phase 2: Build the Baseline

### 1. Inspect recent feedback

Start with `plexus_feedback_analysis` to get the confusion matrix, AC1, and category
summary.

```text
plexus_feedback_analysis(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    days=30,
    output_format="json"
)
```

### 2. Investigate both main segments explicitly

Inspect recent items from each direction separately.

Examples:

```text
plexus_feedback_find(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    initial_value="No",
    final_value="Yes",
    limit=5,
    days=30
)
```

That query targets the `P"No"->A"Yes"` segment.

```text
plexus_feedback_find(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    initial_value="Yes",
    final_value="No",
    limit=5,
    days=30
)
```

That query targets the `P"Yes"->A"No"` segment.

Do not blur the two directions together when forming a hypothesis.

### 3. Lock down a repeatable evaluation dataset

Prefer a deterministic dataset over random spot checks.

Recommended sequence:

1. Check whether the score already has an associated dataset:

```text
plexus_dataset_check_associated(
    scorecard="Quality Assurance v1.0",
    score="Compliance Check"
)
```

2. If not, build one from recent feedback:

```text
plexus_dataset_build_from_feedback_window(
    scorecard="Quality Assurance v1.0",
    score="Compliance Check",
    days=30,
    max_items=200
)
```

### 4. Run the local baseline evaluation

Use `plexus_evaluation_run` with local YAML loading so the evaluation reads the
working copy.

```text
plexus_evaluation_run(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    evaluation_type="accuracy",
    use_score_associated_dataset=true,
    yaml=true,
    notes="Baseline before local feedback-alignment edits"
)
```

Record:

- AC1
- accuracy
- confusion matrix
- any dominant segment such as `P"No"->A"Yes"` or `P"Yes"->A"No"`

## Phase 3: Diagnose the Failure Mode

Use the baseline and the sampled feedback items to classify the problem:

- missing or ambiguous policy
- applicability mixed into the main decision
- evidence not being found reliably
- transcript representation hiding local order
- STT or phonetic confusion
- final aggregation logic too fuzzy or too LLM-driven

This is where `optimizer-cookbook` helps. Choose the smallest change that addresses
the root cause rather than the loudest symptom.

## Phase 4: Edit Locally

Make targeted local changes only.

Common move types:

- prompt clarification
- explicit applicability gate
- extraction before final judgment
- split by criterion or entity
- deterministic aggregation
- transcript processor or input-source changes
- narrow STT-rescue rules for phonetic terms

Implementation references:

- `score-yaml-langgraph` for LangGraph recipes
- `score-yaml-tactusscore` for Tactus recipes

## Phase 5: Sanity Check With Local Predictions

Use `plexus_predict` against the same problematic items you inspected from feedback.

```text
plexus_predict(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    item_ids="item1,item2,item3",
    yaml=true,
    output_format="yaml",
    include_input=true
)
```

Use this to confirm that the edited score now behaves differently on the exact cases
you targeted.

## Phase 6: Re-run the Same Baseline Evaluation

Re-run the same evaluation setup you used for the baseline. Do not switch datasets
or sampling strategy between before and after.

```text
plexus_evaluation_run(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    evaluation_type="accuracy",
    use_score_associated_dataset=true,
    yaml=true,
    notes="Post-edit comparison on same baseline dataset"
)
```

Ask:

- Did AC1 improve?
- Did the targeted segment improve?
- Did the opposite segment get worse?
- Did the change improve only the sampled items, or the broader regression set too?

## Practical Interpretation Rules

- If the targeted segment improves and the opposite segment stays stable, keep the
  change and continue iterating.
- If the targeted segment improves but the opposite segment degrades sharply, the
  change probably overfit one direction.
- If the evaluation is flat but local spot checks look better, the fix may be too
  narrow or the dataset may reveal a second-order regression.
- If the score still fails because it cannot see the right evidence, change the
  input shape or structure before adding more prompt prose.

## What Not to Do

- Do not edit YAML before capturing a baseline.
- Do not mix both main error directions into one hypothesis.
- Do not use release actions during local optimization.
- Do not add large few-shot sets when the real issue is structure or transcript shape.
- Do not treat `NA` as just another class if it is really an applicability question.

## Final Rule

Feedback alignment is not "read a few bad items and tweak the prompt." It is:

1. baseline
2. segment-specific diagnosis
3. local edit
4. local prediction sanity check
5. same-baseline re-evaluation

Only after that should a human decide whether the change is ready to be pushed.

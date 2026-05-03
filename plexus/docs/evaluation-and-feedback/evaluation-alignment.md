# Iterative Evaluation Alignment for Score Configuration Optimization

Systematic process for improving score configurations using evaluation datasets with human-labeled ground truth and local YAML testing.

## Critical Differences from Feedback Alignment

**Evaluation alignment uses LOCAL YAML exclusively** to test your current work-in-progress configuration against datasets with known ground-truth labels. This is fundamentally different from feedback alignment, which analyzes production errors from different score versions.

### Why Use Evaluation Alignment?

1. **Version Control**: Test YOUR current local YAML, not past production versions
2. **Immediate Feedback**: See how your changes perform before pushing to production
3. **Reproducible Results**: Same dataset, same YAML = same results
4. **Rich Context**: Datasets often include edit comments explaining WHY labels are correct

## **CRITICAL SAFETY RULES** ⚠️

### NEVER Pull Score During This Process

**DO NOT run `plexus score pull` at ANY point during evaluation alignment!**

Pulling a score will **OVERWRITE your local work-in-progress YAML** with the remote champion version, destroying your changes.

```bash
# ❌ NEVER DO THIS during evaluation alignment
plexus score pull --scorecard "Quality Assurance" --score "Compliance Check"

# ❌ NEVER DO THIS either through execute_tactus
return plexus.score.pull{ scorecard_identifier = "...", score_identifier = "..." }
```

### ALWAYS Use --yaml Flag for Evaluations

**EVERY evaluation MUST use the `--yaml` flag (or `yaml = true` inside `execute_tactus`)** to load your local YAML.

Without this flag, the evaluation tool will fetch the remote score version and **OVERWRITE your local YAML**.

```bash
# ✅ CORRECT - Uses local YAML
plexus evaluate accuracy --yaml --scorecard "Quality Assurance" --score "Compliance Check"

# ❌ WRONG - Will overwrite local YAML with remote version
plexus evaluate accuracy --scorecard "Quality Assurance" --score "Compliance Check"
```

```lua
# ✅ CORRECT - Uses local YAML
return plexus.evaluation.run{
  scorecard_name = "Quality Assurance",
  score_name = "Compliance Check",
  yaml = true, -- REQUIRED
  n_samples = 20,
}

# ❌ WRONG - Will overwrite local YAML (yaml defaults to True, but be explicit!)
return plexus.evaluation.run{
  scorecard_name = "Quality Assurance",
  score_name = "Compliance Check",
  yaml = false, -- This fetches from API
}
```

## Process Overview

**Who does what:**
- **Main Agent (You - Claude Code)**: Runs evaluations, edits YAML, forms hypotheses, measures improvement
- **evaluation-analyzer sub-agent**: Analyzes confusion matrix segments, identifies patterns
- **evaluation-score-result-analyzer sub-agent**: Examines individual transcripts, extracts edit comment insights

**Iterative workflow:**
1. **Ensure Local YAML Exists**: (Main agent) Verify you have local YAML to work with (pull ONCE at start if needed)
2. **Baseline Evaluation**: (Main agent) Run evaluation using local YAML to establish baseline metrics
3. **Error Analysis**: (Main agent) Delegate to evaluation-analyzer sub-agent to examine specific confusion matrix segment
4. **Hypothesis Formation**: (Main agent) Use patterns from sub-agent to form testable YAML change hypothesis
5. **YAML Modification**: (Main agent) Edit local YAML based on hypothesis
6. **Re-Evaluation**: (Main agent) Run evaluation again with modified YAML
7. **Comparison**: (Main agent) Compare new metrics to baseline - did it improve?
8. **Iterate**: Repeat steps 3-7 until performance meets target or no further improvement possible

## Plexus Runtime APIs (Start Here)

Use the single MCP tool `execute_tactus`. Inside the snippet, call the
host-injected `plexus` module.

**Runtime APIs the Main Agent Uses:**
- `plexus.docs.get`: Always open this doc before starting alignment
- `plexus.api.list`: Discover available runtime namespaces and methods
- `plexus.evaluation.run`: Run evaluations using LOCAL YAML (`yaml = true`) and return confusion matrix and metrics
- `plexus.evaluation.info`: Get detailed results for an existing evaluation ID
- `plexus.score.predict`: Test predictions on specific items using LOCAL YAML (`yaml = true`)
- `Task` tool with `subagent_type="evaluation-analyzer"`: Delegate confusion matrix analysis

**Runtime APIs the Sub-Agents Use:**
- evaluation-analyzer uses: `plexus.evaluation.info` with `include_score_results = true`
- evaluation-score-result-analyzer is deprecated; evaluation-analyzer can inspect score results directly from the evaluation payload

**IMPORTANT**: The `evaluation-analyzer` sub-agent should start with `plexus.evaluation.info{ include_score_results = true }` and inspect the returned score-result metadata before requesting full transcript context elsewhere. Full transcript text should only be fetched selectively for 1-2 items when edit comments are insufficient.

**What These Tools Return:**
Both `plexus.evaluation.run` and `plexus.evaluation.info` return identical structured data:
- `evaluation_id`: Unique evaluation identifier
- `accuracy`: Overall accuracy percentage
- `metrics`: Array of metric objects (Accuracy, Alignment/AC1, Precision, Recall)
- `confusionMatrix`: Matrix with labels array (e.g., ["no", "yes"]) and 2D matrix array
- `predictedClassDistribution`: What the AI predicted (counts and percentages)
- `datasetClassDistribution`: What the ground truth labels are (counts and percentages)

This is **programmatic output** - no analysis or interpretation. The caller analyzes the confusion matrix.

## Phase 0: Initial Setup (ONE-TIME ONLY)

**If you don't have local YAML yet**, pull it ONCE at the very beginning:

```lua
# ✅ ONLY do this ONCE at the start if local YAML doesn't exist
return plexus.score.pull{
  scorecard_identifier = "Quality Assurance v1.0",
  score_identifier = "Compliance Check",
}
```

**After this initial pull, NEVER pull again during the alignment process!**

Verify your local YAML exists:
```bash
ls -la scorecards/Quality\ Assurance\ v1.0/Compliance\ Check.yaml
```

## Phase 1: Baseline Evaluation (LOCAL ONLY)

Establish a quantitative baseline using your current local YAML.

**CRITICAL**: Always use `yaml = true` to ensure local YAML is used.

```lua
return plexus.evaluation.run{
  scorecard_name = "Quality Assurance v1.0",
  score_name = "Compliance Check",
  n_samples = 200, -- or omit for default (10)
  yaml = true,     -- REQUIRED: Use local YAML
}
```

**What This Does:**
- Loads your current local YAML configuration
- Runs predictions on evaluation dataset items
- Compares predictions against ground-truth labels
- Generates confusion matrix, accuracy, AC1 agreement

**Record baseline metrics:**
- Overall accuracy
- Gwet's AC1 (agreement coefficient)
- Confusion matrix (True Positives, False Positives, True Negatives, False Negatives)
- Per-class precision and recall

## Phase 2: Error Analysis with Sub-Agents

**ALWAYS use the `evaluation-analyzer` sub-agent** to examine evaluation results. This agent specializes in analyzing confusion matrix segments and can efficiently examine score results without context overflow.

### Context-Safe Score Result Examination

The evaluation payload is the context-safe starting point:
- **Default**: Use `plexus.evaluation.info{ include_score_results = true }` to inspect predictions, explanations, edit comments, item IDs, and trace data before fetching transcript text.
- **Optional**: Request item transcript text only when needed for detailed analysis (10K+ tokens per item).

**How This Protects Context:**
1. **Main Agent**: Runs evaluations, gets confusion matrix, delegates segment analysis
2. **evaluation-analyzer**: Calls `plexus.evaluation.info{ include_score_results = true }` and filters the returned score results by confusion-matrix segment
3. **Optional**: If edit comments are insufficient, evaluation-analyzer can request transcripts for 1-2 specific items

### Usage Example - Comprehensive Analysis

```lua
# Get the latest evaluation ID first
return plexus.evaluation.info{
  use_latest = true,
  account_key = "call-criteria",
  output_format = "json",
}
```

```python
# Use evaluation-analyzer sub-agent to examine ALL error segments
# The agent will use execute_tactus with plexus.evaluation.info and
# include_score_results = true, then filter locally without transcripts.
Task(
    subagent_type="evaluation-analyzer",
    description="Comprehensive confusion matrix analysis",
    prompt=f"""Analyze ALL error segments from evaluation {evaluation_id}.

    Examine BOTH false positives AND false negatives (5 items each):
    1. Use execute_tactus with plexus.evaluation.info{ evaluation_id='<id>', include_score_results=true } and filter score results locally (no transcripts)
    2. Review edit comments and explanations to identify patterns
    3. If edit comments are insufficient, request transcripts for 1-2 specific items
    4. False positives: What benign patterns trigger false alarms?
    5. False negatives: What violation patterns does AI miss?
    6. Balance analysis: Will fixing one make the other worse?
    7. Provide YAML changes that improve overall accuracy

    Start without transcripts for efficiency. Only request transcripts if absolutely needed."""
)
```

### Usage Example - Focused Analysis (When Requested)

```python
# If main agent specifically wants only one segment analyzed
Task(
    subagent_type="evaluation-analyzer",
    description="Analyze false negative errors only",
    prompt=f"""Analyze ONLY the false negative segment (predicted=no, actual=yes) from evaluation {evaluation_id}.

    Focus on identifying:
    1. What patterns the AI is missing
    2. What edit comments reveal about correct labeling
    3. What YAML changes could fix these errors

    Examine 5 items using execute_tactus with plexus.evaluation.info{ evaluation_id='<id>', include_score_results=true } and local filtering.
    Only request transcripts if edit comments don't provide sufficient detail.
    Note any potential impact on false positives."""
)
```

**Important Notes:**
- **Default behavior is SAFE**: start from `plexus.evaluation.info{ include_score_results = true }` and avoid transcript text
- **Start without transcript text**: Review edit comments, explanations, and trace data first (~26K tokens for 5 items)
- **Request transcript text selectively**: Only use `include_text = true` for 1-2 items when edit comments are insufficient
- The evaluation-analyzer can call the find tool directly with smart context management

**Why This Works:**
- Default behavior without transcript text: 5 items = ~26K tokens (manageable)
- With transcript text when needed: 2 items = ~20K+ tokens (use sparingly)
- Edit comments often provide sufficient detail without needing full transcript text
- Enables efficient examination of many items without context overflow

## Phase 3: Hypothesis Formation

Use error patterns and edit comments to form specific hypotheses:

**From False Negatives (AI Missed Violations):**
- What specific patterns/phrases did AI miss?
- What context clues were present in transcript?
- What do edit comments say about why it should be detected?
- Are there missing criteria in YAML?
- Are thresholds too strict?

**From False Positives (AI Over-Detected):**
- What benign patterns triggered false alarms?
- What context did AI ignore that humans noticed?
- What do edit comments say about why it's NOT a violation?
- Are criteria too broad in YAML?
- Are thresholds too lenient?

**Example Hypothesis:**
```
Hypothesis: AI is missing "implicit medication review" patterns where agent
confirms medication without explicitly saying "medication review".
Edit comments indicate phrases like "let me verify your medications" and
"checking your current prescriptions" should count as medication review.

Proposed YAML change: Add explicit_patterns for implicit review language.
```

## Phase 4: YAML Modification

Edit your local YAML based on hypotheses. **DO NOT pull - edit the existing local file!**

```bash
# ✅ Edit existing local file
vim scorecards/Quality\ Assurance\ v1.0/Compliance\ Check.yaml

# ❌ NEVER pull during alignment
# plexus score pull  # NO! This overwrites your changes!
```

**Example YAML Changes:**

For false negatives (missed detections):
```yaml
# Add missing patterns
explicit_patterns:
  - "let me verify your medications"
  - "checking your current prescriptions"
  - "reviewing your medication list"

# Lower threshold if using confidence-based logic
threshold: 0.6  # was 0.7
```

For false positives (over-detection):
```yaml
# Add exclusion patterns
exclusion_patterns:
  - "I don't have access to medications"
  - "you'll need to check with your doctor"

# Raise threshold
threshold: 0.8  # was 0.7
```

## Phase 5: Re-Evaluation (LOCAL ONLY)

Test your YAML changes against the same dataset.

**CRITICAL**: Use `yaml = true` again.

```lua
# ✅ CORRECT - Uses your modified local YAML
return plexus.evaluation.run{
  scorecard_name = "Quality Assurance v1.0",
  score_name = "Compliance Check",
  n_samples = 200, -- Same sample size as baseline
  yaml = true,     -- REQUIRED
  latest = false,
}
```

**Compare to baseline:**
- Did accuracy improve?
- Did AC1 agreement improve?
- Did target confusion matrix segment improve (e.g., fewer false negatives)?
- Did we introduce new problems (e.g., more false positives)?

## Phase 6: Iteration

**If metrics improved:**
- Document what changed and why
- Consider additional refinements
- Test on edge cases using `plexus.score.predict` with `yaml = true`

**If metrics regressed:**
- Revert YAML changes
- Re-examine error patterns
- Form new hypothesis
- Try different approach

**If metrics stayed flat:**
- Hypothesis may be wrong
- Analyze different error segment
- Consider dataset quality issues

## Prediction Testing (LOCAL ONLY)

Test specific items using local YAML to validate behavior:

```lua
# ✅ Test single item with local YAML
return plexus.score.predict{
  scorecard_name = "Quality Assurance v1.0",
  score_name = "Compliance Check",
  item_id = "88ed6e27-b5ae-4641-b024-d47f4c6ba631",
  yaml = true,          -- REQUIRED: Use local YAML
  include_input = true,
  include_trace = true, -- See detailed execution
  output_format = "yaml",
}

# ✅ Test multiple items with local YAML
return plexus.score.predict{
  scorecard_name = "Quality Assurance v1.0",
  score_name = "Compliance Check",
  item_ids = "item1,item2,item3",
  yaml = true, -- REQUIRED: Use local YAML
  output_format = "yaml",
}
```

## Complete Workflow Example

### 1. Initial Setup (ONCE)
```lua
# Only if local YAML doesn't exist - DO THIS ONCE
return plexus.score.pull{
  scorecard_identifier = "Quality Assurance v1.0",
  score_identifier = "Compliance Check",
}
```

### 2. Baseline Evaluation
```lua
return plexus.evaluation.run{
  scorecard_name = "Quality Assurance v1.0",
  score_name = "Compliance Check",
  n_samples = 200,
  yaml = true, -- REQUIRED
}
```

Record: Accuracy=0.75, AC1=0.68, FN=25, FP=15

### 3. Error Analysis with Sub-Agents
```lua
# Get latest evaluation
return plexus.evaluation.info{ use_latest = true }
```

```python
eval_id = "evaluation_123"
# Use evaluation-analyzer sub-agent to examine ALL error segments
Task(
    subagent_type="evaluation-analyzer",
    description="Comprehensive confusion matrix analysis",
    prompt=f"""Analyze ALL error segments from evaluation {eval_id}.

    Examine both false positives AND false negatives (3-5 items each).
    Provide balanced YAML change recommendations that improve overall accuracy.
    Consider trade-offs between error types."""
)
```

Sub-agent returns (synthesized from score result examination without transcripts):
```
Confusion Matrix: TP: 150 | FP: 15 | TN: 120 | FN: 25
Accuracy: 0.75 | AC1: 0.68

FALSE POSITIVES (15 items, examined 5 without transcripts):
Pattern: AI explanation shows it detects implicit medication review language even when
agent is discussing non-medication topics (e.g., "let me check your appointment").
Edit comments: "Not medication review - general inquiry"
Item IDs: item-001, item-003, item-007 (can examine with transcripts if needed)

FALSE NEGATIVES (25 items, examined 5 without transcripts):
Pattern: AI explanation shows it misses implicit medication review when phrased as questions.
Edit comments: "This is medication verification - should count as review"
Example explanations reference phrases like "Are you still taking X?" being overlooked.
Item IDs: item-012, item-015, item-023 (can examine with transcripts if needed)

BALANCED RECOMMENDATION:
1. Add exclusion context: "checking appointment|checking availability" (reduces FPs)
2. Add question patterns: "are you (still)? taking|do you take" (reduces FNs)
3. Expected impact: FN: 25→12, FP: 15→10, Accuracy: 0.75→0.82

TRADE-OFF: Minimal - exclusions are specific enough to not affect FN reduction.

Note: Edit comments provided sufficient detail. No transcripts needed for this analysis.
```

### 4. Form Hypothesis (Based on Balanced Analysis)
```
Hypothesis: AI has two issues:
  1. Over-detects "checking" language as medication review (FPs)
  2. Misses question-based medication verification (FNs)

Changes:
  1. Add exclusion patterns for non-medication "checking" contexts
  2. Add detection patterns for question-based verification

Expected impact:
  - FN: 25→12 (52% reduction)
  - FP: 15→10 (33% reduction)
  - Overall accuracy: 0.75→0.82
```

### 5. Edit Local YAML
```bash
# ✅ Edit existing file (don't pull!)
vim scorecards/Quality\ Assurance\ v1.0/Compliance\ Check.yaml
```

Add both detection and exclusion patterns:
```yaml
# Reduce false negatives - add question-based patterns
explicit_patterns:
  - "are you (still)? taking"
  - "do you take"
  - "have you been taking"

# Reduce false positives - exclude non-medication contexts
exclusion_patterns:
  - "checking (your)? appointment"
  - "checking (your)? availability"
  - "let me check the schedule"
```

### 6. Re-Evaluate
```lua
# ✅ Test modified local YAML
return plexus.evaluation.run{
  scorecard_name = "Quality Assurance v1.0",
  score_name = "Compliance Check",
  n_samples = 200,
  yaml = true, -- REQUIRED
}
```

New results: Accuracy=0.82, AC1=0.76, FN=12, FP=10

**Success!** Both error types improved:
- False negatives: 25→12 (52% reduction) ✅
- False positives: 15→10 (33% reduction) ✅
- Overall accuracy: 0.75→0.82 (9% improvement) ✅

### 7. Iterate on Remaining Errors
```python
# Continue using efficient examination without transcripts first
Task(
    subagent_type="evaluation-analyzer",
    description="Analyze remaining false negatives",
    prompt=f"""Analyze remaining 12 false negatives from latest evaluation.

    Use execute_tactus with plexus.evaluation.info{ evaluation_id='<id>', include_score_results=true } and filter locally to examine 5 items.
    Review edit comments and explanations to identify what patterns are still being missed.
    Only request transcripts if edit comments don't provide sufficient detail."""
)
```

### 8. When Done, Push Changes
Only after alignment is complete and explicitly approved, use the release workflow
for score updates. Do not push or promote changes as part of the iterative
alignment loop.

## Dataset Considerations

### Evaluation Datasets with Edit Comments

Evaluation datasets often include rich metadata:
- `ground_truth_label`: The correct classification
- `edit_comment`: Human explanation of WHY label is correct
- `item.text`: Full transcript or document text
- `item.identifiers`: External IDs for traceability

**Edit comments are gold!** They explain human reasoning and often point directly to what the AI should have detected.

### Dataset Sources

```yaml
# FeedbackItems dataset (from production corrections)
class: FeedbackItems
scorecard: 1438
score: "Medication Review"
days: 30
limit: 200
balance: True  # Balance classes for fair evaluation
```

```yaml
# ManualReview dataset (from human-labeled samples)
class: ManualReview
scorecard: 1438
review_batch: "Q1-2025-audit"
limit: 100
```

## Advanced Techniques

### A/B Testing with Different Thresholds

Test multiple threshold values:
```lua
# Test threshold=0.6
# (edit YAML, set threshold: 0.6)
return plexus.evaluation.run{ scorecard_name = "Quality Assurance v1.0", score_name = "Compliance Check", yaml = true }

# Test threshold=0.7
# (edit YAML, set threshold: 0.7)
return plexus.evaluation.run{ scorecard_name = "Quality Assurance v1.0", score_name = "Compliance Check", yaml = true }

# Test threshold=0.8
# (edit YAML, set threshold: 0.8)
return plexus.evaluation.run{ scorecard_name = "Quality Assurance v1.0", score_name = "Compliance Check", yaml = true }
```

Compare metrics to find optimal threshold.

### Pagination for Large Result Sets

The `evaluation-analyzer` can examine multiple batches of items using the offset parameter:

```python
# First, examine 5 items without transcripts
Task(
    subagent_type="evaluation-analyzer",
    description="Initial false negative analysis",
    prompt=f"""Analyze false negatives from evaluation {eval_id}.

    Use execute_tactus with plexus.evaluation.info{ include_score_results=true } and filter locally with:
    - predicted_value: "no"
    - actual_value: "yes"
    - limit: 5
    - offset: 0
    (include_text defaults to false)

    Identify initial patterns from edit comments and explanations."""
)

# If needed, examine the next batch
Task(
    subagent_type="evaluation-analyzer",
    description="Extended false negative analysis",
    prompt=f"""Continue analyzing false negatives from evaluation {eval_id}.

    Use offset: 5 to examine the next batch of items.
    Compare patterns to the first batch. Are the same issues recurring?"""
)
```

The offset/limit parameters allow you to walk through large result sets efficiently without overwhelming context, especially when using the default behavior (no transcripts).

### Focus on Specific Confusion Matrix Cells

```python
# Analyze false positives only
Task(
    subagent_type="evaluation-analyzer",
    description="Analyze false positives",
    prompt=f"""Analyze false positive segment (predicted=yes, actual=no) from evaluation {eval_id}.

    Use execute_tactus with plexus.evaluation.info{ include_score_results=true } and local filtering to examine 5 items.
    Focus on edit comments to identify what benign patterns triggered false alarms.
    Only request transcripts if edit comments are unclear."""
)

# Analyze true negatives to understand what AI correctly rejects
Task(
    subagent_type="evaluation-analyzer",
    description="Analyze true negatives",
    prompt=f"""Analyze true negative segment (predicted=no, actual=no) from evaluation {eval_id}.

    Examine 5 items using default parameters (no transcripts).
    Review what patterns AI correctly rejects based on edit comments and explanations."""
)
```

### Multi-Score Evaluation

Evaluate entire scorecard:
```lua
return plexus.evaluation.run{
  scorecard_name = "Quality Assurance v1.0",
  -- No score_name = evaluate all scores in scorecard
  yaml = true,
}
```

## Implementation Checklist

**Before Starting:**
- [ ] Verify local YAML exists (pull ONCE if needed)
- [ ] Understand evaluation dataset (check for edit comments)
- [ ] Note baseline metrics to measure improvement

**During Each Iteration (Main Agent):**
- [ ] Run evaluation with `plexus.evaluation.run{ scorecard_name = "...", score_name = "...", yaml = true }`
- [ ] Delegate to `evaluation-analyzer` sub-agent with evaluation_id and target segment
- [ ] Review pattern insights from sub-agent
- [ ] Form specific, testable hypothesis based on patterns
- [ ] Edit local YAML (NEVER pull!)
- [ ] Re-run evaluation with same parameters
- [ ] Compare new metrics to baseline
- [ ] Document what changed and why

**What Sub-Agents Do (Automatic):**
- [ ] evaluation-analyzer: Gets confusion matrix, calls `plexus.evaluation.info{ include_score_results = true }`, filters score results locally without transcript text, examines edit comments and explanations, optionally requests transcript text for 1-2 items if needed, returns concise insights

**Never:**
- [ ] ❌ Run `plexus score pull` after initial setup
- [ ] ❌ Run evaluation without `yaml = true`
- [ ] ❌ Request transcript text (`include_text = true`) for many items at once
- [ ] ❌ Push changes without testing first

**Always:**
- [ ] ✅ Main agent runs evaluations with `plexus.evaluation.run`
- [ ] ✅ Main agent delegates analysis to `evaluation-analyzer` sub-agent
- [ ] ✅ evaluation-analyzer starts with default parameters (no transcript text) for efficiency
- [ ] ✅ Use `yaml = true` for evaluations and predictions
- [ ] ✅ Edit local YAML files directly (don't pull!)
- [ ] ✅ Compare metrics to baseline after each change

## Troubleshooting

### "My changes aren't reflected in evaluation results"

**Cause:** Evaluation ran without `yaml = true` and pulled remote version, overwriting your local YAML.

**Fix:**
1. Restore your local YAML from backup or git
2. Always use `yaml = true` in all evaluation calls

### "I accidentally pulled and lost my changes"

**Cause:** Ran `plexus score pull` during alignment process.

**Fix:**
1. Check git history: `git diff scorecards/...`
2. Restore from git if committed: `git restore scorecards/...`
3. If no git backup, you'll need to redo YAML changes

**Prevention:** NEVER run `plexus score pull` after initial setup!

### "Sub-agent isn't providing useful insights"

**Cause:** Prompt may not be specific enough about what to analyze, or edit comments might be insufficient.

**Fix:** Be explicit and focus on patterns:
```python
Task(
    subagent_type="evaluation-analyzer",
    description="Analyze false negative patterns",
    prompt=f"""Analyze false negative segment (predicted=no, actual=yes) from evaluation {eval_id}.

    Use execute_tactus with plexus.evaluation.info{ evaluation_id='<id>', include_score_results=true } and local filtering to examine 5 items.
    Focus on identifying:
    - Common patterns AI is missing (based on edit comments and explanations)
    - What edit comments reveal about labeling criteria
    - Specific YAML changes that could fix these errors

    If edit comments don't provide enough detail, request transcripts for 1-2 specific items.
    Your job is to synthesize patterns across items."""
)
```

**Remember:**
- Start with default parameters (no transcript text) - edit comments often provide sufficient detail
- Request transcript text only when edit comments are unclear or missing
- The AI's own explanation field often reveals what it was looking for (and why it missed/detected)
- Item IDs are included so you can follow up on specific items if needed

### "Metrics aren't improving"

**Possible causes:**
- Hypothesis is wrong (test different error segment)
- Dataset may have labeling errors (review edit comments)
- Changes are too conservative (try more aggressive patterns)
- Changes are conflicting (revert and try one change at a time)

**Debug approach:**
1. Use `plexus.score.predict` with `yaml = true` on specific failing items
2. Add `include_trace = true` to see detailed execution
3. Verify your YAML changes are being loaded (check trace output)
4. Test hypothesis on single item before re-evaluating full dataset

## Summary

**Evaluation alignment is the safest way to improve scores** because:
1. You test your current local YAML (not past production versions)
2. You see immediate feedback on your changes
3. You can iterate rapidly without affecting production
4. You have rich context (edit comments) explaining ground truth

**Remember the golden rules:**
- ⚠️ **NEVER `plexus score pull` after initial setup**
- **ALWAYS use `yaml = true` for evaluations and predictions**
- ⚠️ **ALWAYS use `evaluation-analyzer` sub-agent for result analysis**
- ⚠️ **START with default behavior (no transcript text) for efficiency**
- ⚠️ **REQUEST transcript text sparingly (1-2 items) when edit comments are insufficient**

Follow this process and you'll safely improve your scores with measurable, reproducible results.

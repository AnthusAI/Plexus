# Iterative Feedback Alignment for Score Configuration Optimization

Systematic process for improving score configurations using human feedback data and prediction testing.

## Process Overview

1. **Performance Analysis**: Get baseline metrics and identify primary error patterns
2. **Baseline Evaluation (LOCAL ONLY)**: Run a full baseline evaluation using a dataset aligned to your feedback items
3. **Error Investigation**: Examine specific failure cases and human corrections  
4. **Prediction Testing (LOCAL ONLY)**: Test current configuration on problematic items
5. **Configuration Optimization**: Iterate based on analysis results, re-evaluating after each change

## MCP Tools (Start Here)

Use MCP tools for token-efficient structured output:
- `get_plexus_documentation`: Always open this doc before starting alignment
- `think`: Required planning step; enforces baseline-first workflow
- `plexus_feedback_analysis`: Performance metrics and error patterns
- `plexus_feedback_find`: Specific feedback items with human corrections
- `plexus_predict`: Test predictions against known ground-truth (LOCAL YAML mode)
- `run_plexus_evaluation`: Run evaluations (LOCAL mode) for baseline and post-change comparisons

## Phase 1: Performance Analysis

Get comprehensive performance summary:

```
plexus_feedback_analysis(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    days=14,
    output_format="json"
)
```

 Prioritize Gwet's AC1 (agreement) over raw accuracy for alignment decisions. Focus on confusion matrix to identify:
## Phase 2: Baseline Evaluation (LOCAL ONLY) — Do this BEFORE editing YAML

Establish a quantitative baseline before changing any YAML so improvements are measurable and attributable.

1) Prepare a dataset that mirrors the feedback items you will optimize against (see Dataset section below).

2) Run a baseline evaluation in LOCAL mode. IMPORTANT: Always set an absolute override folder to your local scorecards directory.

```
run_plexus_evaluation(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",      # optional; evaluate a single score if desired
    n_samples=200,                       # or omit to use dataset size
    remote=False,                        # LOCAL ONLY
    yaml=True,                           # load from local YAML
    ctx={"override_folder":"/home/<user>/projects/Plexus/scorecards"}
)
```

Record AC1, accuracy, and confusion matrix as your baseline.

Note: Do not push or promote versions during this phase; iterate strictly on local YAML.
- False positives: AI over-detecting
- False negatives: AI missing violations
- Primary error pattern for investigation

## Phase 3: Error Investigation

Examine primary error pattern from Phase 1:

```
# For false negatives (AI missed violations) - paginated results
plexus_feedback_find(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    initial_value="No",
    final_value="Yes",
    limit=5,
    days=14
)
```

Results include full item details nested within each feedback edit, eliminating need for separate item_info calls. 
Analyze `edit_comment` fields and `item_details.text` for configuration gaps. Look for patterns in missed behaviors.

Use pagination for larger datasets:
```
# Get next page using next_page_start_id from previous response
plexus_feedback_find(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    initial_value="No", 
    final_value="Yes",
    limit=5,
    next_page_start_id="feedback_item_123"
)
```

Examine secondary error pattern:

```
# For false positives (AI over-detected) 
plexus_feedback_find(
    scorecard_name="Quality Assurance v1.0", 
    score_name="Compliance Check",
    initial_value="Yes",
    final_value="No",
    limit=5,
    days=14
)
```

## Phase 4: Prediction Testing (LOCAL ONLY)

Test current configuration on items with known ground-truth:

```
plexus_predict(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check", 
    item_id="88ed6e27-b5ae-4641-b024-d47f4c6ba631",
    output_format="yaml",
    include_input=true,
    yaml_only=true                # LOCAL YAML ONLY
)
```

Test multiple related items:

```
plexus_predict(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    item_ids="item1,item2,item3,item4,item5",
    output_format="yaml",
    yaml_only=true                # LOCAL YAML ONLY
)
```

Compare predictions against feedback ground-truth labels.

## Phase 5: Configuration Optimization

**False Negatives**: Add specific violation patterns, lower thresholds, include examples from edit comments
**False Positives**: Add exceptions, refine criteria, raise thresholds, include counterexamples

Test configuration changes:

```
plexus_predict(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    item_ids="known_problematic_items", 
    output_format="yaml"
)
```

## Dataset Setup (Align to Feedback)

Use a dataset that represents the same distribution as your feedback items to ensure evaluation reflects alignment targets. See `dataset-yaml-format.md` for full schema. Example minimal dataset YAML:

```yaml
name: Feedback-Aligned Dataset
source:
  type: FeedbackItems
  scorecard: 1438                # your scorecard ID
  score: "Compliance Check"      # your score name
  days: 30
  limit: 500
  balance: false                 # or true if you want class balancing
transformations: []
metadata:
  purpose: baseline-evaluation
```

FeedbackItems dataset (score YAML-style fields):

```yaml
class: FeedbackItems
scorecard: 1438
score: "Medication Review"
days: 30
limit: 100
limit_per_cell: 50
balance: false
```

Load or refresh dataset as needed with the dataset loader (LOCAL context):

```
plexus_dataset_load(
    source_identifier="Feedback-Aligned Dataset",
    fresh=true
)
```

## Complete Workflow

### 1. Baseline Summary
```
plexus_feedback_analysis(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check", 
    days=30,
    output_format="json"
)
```

### 2. Investigation
```
plexus_feedback_find(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    initial_value="No",
    final_value="Yes",
    limit=5,
    days=30
)
```

### 3. Baseline Evaluation (LOCAL ONLY) — With override_folder
```
run_plexus_evaluation(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    remote=False,
    yaml=True,
    ctx={"override_folder":"/home/<user>/projects/Plexus/scorecards"}
)
```

### 4. Testing (LOCAL ONLY)
```
plexus_predict(
    scorecard_name="Quality Assurance v1.0", 
    score_name="Compliance Check",
    item_ids="problematic_item_ids_from_feedback",
    output_format="yaml",
    include_input=true
)
```

### 5. Optimization
- Modify configuration based on analysis
- Deploy new version
- Test on same items

### 6. Validation (LOCAL ONLY)
```
plexus_predict(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check", 
    item_ids="same_test_items",
    output_format="yaml"
)
```

### 7. Impact Measurement
```
plexus_feedback_analysis(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    days=7,
    output_format="json"
)
```

## Advanced Techniques

**Pattern Discovery**: Larger samples for systemic analysis
```
plexus_feedback_find(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check", 
    limit=5,
    days=30,
    prioritize_edit_comments=true
)
```

**A/B Testing**: Compare baseline vs modified configurations on same test items

**Pagination for Large Datasets**: Use pagination to analyze large volumes of feedback
```
# Get multiple pages of feedback items
first_page = plexus_feedback_find(..., limit=5)
second_page = plexus_feedback_find(..., limit=5, next_page_start_id=first_page.pagination.next_page_start_id)
```

**Nested Item Details**: Each feedback result includes full item information
- `item_details.text`: Original call transcript or document text
- `item_details.external_id`: External system identifier  
- `item_details.identifiers`: Additional identifying information
- Eliminates need for separate `plexus_item_info` calls

**Continuous Monitoring**: Weekly performance tracking
```
plexus_feedback_analysis(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    days=7, 
    output_format="json"
)
```

## Implementation Notes

- Start with summary analysis, follow confusion matrix recommendations
- Run a LOCAL baseline evaluation before any edits; use the same dataset for post-change comparison
- Prioritize improving Gwet's AC1 (agreement) while monitoring accuracy and class balance
- Use feedback items as ground-truth labels for validation
- Test before/after configuration changes in LOCAL YAML mode (yaml_only / yaml=True)
- Focus on edit comments for root cause analysis
- Maintain test sets for regression testing
- Measure improvement with AC1, confusion matrix shifts, and stability across segments

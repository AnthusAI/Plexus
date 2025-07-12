# Iterative Feedback Alignment for Score Configuration Optimization

Systematic process for improving score configurations using human feedback data and prediction testing.

## Process Overview

1. **Performance Analysis**: Get baseline metrics and identify primary error patterns
2. **Error Investigation**: Examine specific failure cases and human corrections  
3. **Prediction Testing**: Test current configuration on problematic items
4. **Configuration Optimization**: Iterate based on analysis results

## MCP Tools

Use MCP tools for token-efficient structured output:
- `plexus_feedback_summary`: Performance metrics and error patterns
- `plexus_feedback_find`: Specific feedback items with human corrections
- `plexus_predict`: Test predictions against known ground-truth

## Phase 1: Performance Analysis

Get comprehensive performance summary:

```
plexus_feedback_summary(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    days=14,
    output_format="json"
)
```

Prioritize AC1 over accuracy for analysis decisions. Focus on confusion matrix to identify:
- False positives: AI over-detecting
- False negatives: AI missing violations
- Primary error pattern for investigation

## Phase 2: Error Investigation

Examine primary error pattern from Phase 1:

```
# For false negatives (AI missed violations)
plexus_feedback_find(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    initial_value="No",
    final_value="Yes",
    limit=10,
    days=14,
    output_format="yaml"
)
```

Analyze `edit_comment` fields for configuration gaps. Look for patterns in missed behaviors.

Examine secondary error pattern:

```
# For false positives (AI over-detected)
plexus_feedback_find(
    scorecard_name="Quality Assurance v1.0", 
    score_name="Compliance Check",
    initial_value="Yes",
    final_value="No",
    limit=5,
    days=14,
    output_format="yaml"
)
```

## Phase 3: Prediction Testing

Test current configuration on items with known ground-truth:

```
plexus_predict(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check", 
    item_id="88ed6e27-b5ae-4641-b024-d47f4c6ba631",
    output_format="yaml",
    include_input=true
)
```

Test multiple related items:

```
plexus_predict(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    item_ids="item1,item2,item3,item4,item5",
    output_format="yaml"
)
```

Compare predictions against feedback ground-truth labels.

## Phase 4: Configuration Optimization

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

## Complete Workflow

### 1. Baseline
```
plexus_feedback_summary(
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
    limit=15,
    days=30,
    output_format="yaml"
)
```

### 3. Testing
```
plexus_predict(
    scorecard_name="Quality Assurance v1.0", 
    score_name="Compliance Check",
    item_ids="problematic_item_ids_from_feedback",
    output_format="yaml",
    include_input=true
)
```

### 4. Optimization
- Modify configuration based on analysis
- Deploy new version
- Test on same items

### 5. Validation
```
plexus_predict(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check", 
    item_ids="same_test_items",
    output_format="yaml"
)
```

### 6. Impact Measurement
```
plexus_feedback_summary(
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
    limit=50,
    days=30,
    output_format="yaml",
    prioritize_edit_comments=true
)
```

**A/B Testing**: Compare baseline vs modified configurations on same test items

**Continuous Monitoring**: Weekly performance tracking
```
plexus_feedback_summary(
    scorecard_name="Quality Assurance v1.0",
    score_name="Compliance Check",
    days=7, 
    output_format="json"
)
```

## Implementation Notes

- Start with summary analysis, follow confusion matrix recommendations
- Use feedback items as ground-truth labels for validation
- Test before/after configuration changes
- Focus on edit comments for root cause analysis
- Maintain test sets for regression testing
- Measure actual improvement with metrics

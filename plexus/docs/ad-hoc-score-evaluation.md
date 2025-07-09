# Ad-Hoc Score evaluation

Here's how you can test score results to see if score configurations are working, and if they're producing the expected values.

## IMPORTANT: Always Start with Summary Analysis

**Before examining individual feedback items, you MUST run a summary analysis to understand the overall performance and identify which specific segments need investigation.**

### Why Summary First?

Individual feedback items only tell part of the story. Without understanding the overall accuracy, confusion matrix, and agreement patterns, you might:

- Focus on the wrong types of errors
- Miss systematic problems 
- Waste time examining random items instead of problematic patterns
- Draw incorrect conclusions from limited samples

The summary provides the "big picture" that guides effective analysis.

## Getting Overall Performance Summary

Use the `plexus feedback summary` command to get comprehensive analysis including confusion matrix, accuracy, AC1 agreement, and actionable recommendations:

```bash
plexus feedback summary --scorecard "Quality Assurance v1.0" --score "Compliance Check"
```

### Summary Output Includes:

1. **Overall Accuracy**: Percentage of cases where AI and human reviewers agreed
2. **Gwet's AC1 Agreement Coefficient**: Measures inter-rater reliability accounting for chance agreement
3. **Confusion Matrix**: Shows patterns of AI predictions vs human corrections
4. **Precision and Recall**: Classification performance metrics
5. **Class Distribution**: How feedback is distributed across answer categories
6. **Actionable Recommendations**: Specific next steps based on the analysis

### Example Summary Analysis:

```yaml
# Feedback Summary Analysis
# Scorecard: Quality Assurance v1.0
# Score: Compliance Check
# Period: Last 14 days

context:
  scorecard_name: "Quality Assurance v1.0"
  score_name: "Compliance Check"
  total_found: 87
  filters:
    days: 14
    
analysis:
  accuracy: 78.2
  ac1: 0.64
  total_items: 87
  agreements: 68
  disagreements: 19
  
  confusion_matrix:
    labels: ["No", "Yes"]
    matrix:
      - actualClassLabel: "No"
        predictedClassCounts:
          "No": 62
          "Yes": 8
      - actualClassLabel: "Yes"  
        predictedClassCounts:
          "No": 11
          "Yes": 6
          
  precision: 42.9
  recall: 35.3
  
  class_distribution:
    - label: "No"
      count: 70
    - label: "Yes"
      count: 17
      
  warning: "Imbalanced classes"

recommendation: "Moderate accuracy - room for improvement. Focus on minority class prediction accuracy. Use `find` with specific value filters to examine false positives and negatives."
```

### Interpreting Summary Results:

**Accuracy (78.2%)**: Moderate performance - significant room for improvement

**AC1 (0.64)**: Fair agreement between AI and human reviewers
- < 0.4: Poor agreement
- 0.4-0.6: Fair agreement  
- 0.6-0.8: Good agreement
- > 0.8: Excellent agreement

**Confusion Matrix**: Shows the AI is over-predicting "No" (62 correct, 8 false positives) and under-predicting "Yes" (6 correct, 11 false negatives)

**Class Imbalance**: 70 "No" vs 17 "Yes" - the AI struggles with the minority "Yes" class

**Recommendation**: Focus on false negatives (AI said "No" but human said "Yes") and false positives (AI said "Yes" but human said "No")

## Following Summary Recommendations

Based on the summary analysis above, here's how to drill down:

### 1. Examine False Negatives (AI missed violations)
```bash
# AI predicted "No" but humans corrected to "Yes" 
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --initial-value "No" --final-value "Yes" --limit 10
```

### 2. Examine False Positives (AI over-detected violations)
```bash
# AI predicted "Yes" but humans corrected to "No"
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --initial-value "Yes" --final-value "No" --limit 10
```

### 3. Look for Patterns in Edit Comments
```bash
# Get items with human explanations about why predictions were wrong
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --limit 15 --format yaml
```

## Finding Feedback Items for Score Improvement

After running the summary analysis and identifying the key problem areas, use the `plexus feedback find` command to examine specific feedback patterns:

### Basic Feedback Search

```bash
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --limit 10
```

This will show the 10 most recent feedback items for that score, prioritizing items with edit comments (which indicate human corrections).

### Finding Specific Value Changes

To find cases where predictions were changed from one value to another:

```bash
# Find cases where "No" was changed to "Yes" (false negatives)
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --initial-value "No" --final-value "Yes" --limit 5

# Find cases where "Yes" was changed to "No" (false positives)  
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --initial-value "Yes" --final-value "No" --limit 5
```

### YAML Output for Analysis

For detailed analysis and easy parsing, use YAML format:

```bash
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --limit 5 --format yaml
```

Example YAML output:

```yaml
# Plexus feedback search results
context:
  command: plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --limit 5 --format yaml
feedback_items:
  - item_id: "88ed6e27-b5ae-4641-b024-d47f4c6ba631"
    initial_value: "No"
    final_value: "Yes"
    initial_explanation: "The agent made several statements that could be considered misleading..."
    final_explanation: ""
    edit_comment: "Agent did not make any misleading statements. Information provided was accurate."
    edited_by: "QA Manager"
    edited_at: "2025-06-10T07:14:58.267Z"
    external_id: "57011537"
  - item_id: "6ded9491-5909-4a7c-8642-c9a4a61db404"
    initial_value: "Yes"
    final_value: "No"
    initial_explanation: "Agent made misleading claims about coverage..."
    edit_comment: "Agent statements were within policy guidelines after review."
    edited_by: "QA Manager"
    edited_at: "2025-06-09T14:22:15.123Z"
    external_id: "57011234"
```

### Recent Feedback Analysis

Look at recent feedback to understand current issues:

```bash
# Get feedback items from the last 7 days
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --days 7 --limit 20

# Get feedback items from the last 30 days (default)
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --limit 20
```

### Complete Workflow: From Summary to Score Improvement

1. **Start with Summary Analysis** ⭐ **REQUIRED FIRST STEP**
   ```bash
   plexus feedback summary --scorecard "Quality Assurance v1.0" --score "Compliance Check" --days 14
   ```

2. **Analyze the confusion matrix** to understand error patterns:
   - High false positives? AI is over-detecting violations
   - High false negatives? AI is missing violations  
   - Balanced errors? May need general refinement

3. **Follow the recommendation** provided in the summary to target specific problem areas

4. **Examine specific error types** based on confusion matrix:
   ```bash
   # For false negatives (most common issue)
   plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --initial-value "No" --final-value "Yes" --limit 10 --format yaml
   ```

5. **Look for patterns in edit comments** to understand why humans corrected the predictions:
   - `initial_value` → `final_value`: What was changed
   - `edit_comment`: Why it was changed (most important)
   - `initial_explanation`: What the AI originally thought

6. **Test current behavior** on problematic items:
   ```bash
   plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --item "ITEM_ID_FROM_FEEDBACK" --format yaml
   ```

7. **Compare and improve**: Use the gap between current predictions and feedback corrections to refine the score configuration

## Single Prediction

You can check one score prediction with the `plexus predict` command:

```
plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml
```

This produces token-efficient YAML output that includes the prediction results with context:

```yaml
# Plexus prediction results
context:
  description: Output from plexus predict command
  command: plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml
predictions:
  - item_id: d0971986-3838-4066-80ea-548b90a27f4d
    scores:
      - name: "Compliance Check"
        value: "No"
        explanation: "The agent did not make any non-compliant statements during the call. All information provided was accurate and within policy guidelines."
```

## Multiple Items

You can predict on multiple items at once using the `--items` option with a comma-separated list:

```
plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --items "6ded9491-5909-4a7c-8642-c9a4a61db404,a312c48c-d2bd-4e5c-bd2a-126e4a992ee6,3e9ac926-c376-44b7-8e70-12a6202958bb" --format yaml
```

Example output for multiple items:

```yaml
# Plexus prediction results
context:
  description: Output from plexus predict command
  command: plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --items "6ded9491-5909-4a7c-8642-c9a4a61db404,a312c48c-d2bd-4e5c-bd2a-126e4a992ee6,3e9ac926-c376-44b7-8e70-12a6202958bb" --format yaml
predictions:
  - item_id: 6ded9491-5909-4a7c-8642-c9a4a61db404
    scores:
      - name: "Compliance Check"
        value: "No"
        explanation: "The agent provided accurate information throughout the call."
  - item_id: a312c48c-d2bd-4e5c-bd2a-126e4a992ee6
    scores:
      - name: "Compliance Check"
        value: "No"
        explanation: "No non-compliant statements were identified."
  - item_id: 3e9ac926-c376-44b7-8e70-12a6202958bb
    scores:
      - name: "Compliance Check"
        value: "Yes"
        explanation: "The agent made statements that did not align with policy guidelines."
```

## Including Input Data

To include the original input text and metadata in the output, use the `--input` flag:

```
plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml --input
```

Example output with input data:

```yaml
# Plexus prediction results
context:
  description: Output from plexus predict command
  command: plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml --input
  scorecard_id: 59125ba2-670c-4aa5-b796-c2085cf38a0c
  item_count: 1
  score_id: 69e2adba-553e-49a3-9ede-7f9a679a08f3
predictions:
  - item_id: d0971986-3838-4066-80ea-548b90a27f4d
    input:
      text: "Agent: Good morning! Thank you for calling our company. How can I help you today?\nCustomer: Hi, I'm interested in getting a quote for insurance..."
      metadata:
        call_duration: 15.5
        agent_id: "AG001"
        customer_type: "new"
    scores:
      - name: "Compliance Check"
        value: "No"
        explanation: "The agent did not make any non-compliant statements during the call. All information provided was accurate and within policy guidelines."
```

## Including Execution Trace

For debugging or detailed analysis, include the full execution trace with the `--trace` flag:

```
plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml --trace
```

This adds detailed execution information to help understand how the prediction was made.

## Multiple Predictions (Shell Commands)

If you want to run quick checks on multiple items with shell commands, you can use the `--items` option and extract specific values:

```bash
echo "Checking multiple items for Compliance Check:"
plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --items "6ded9491-5909-4a7c-8642-c9a4a61db404,a312c48c-d2bd-4e5c-bd2a-126e4a992ee6,3e9ac926-c376-44b7-8e70-12a6202958bb" --format yaml | grep -A 2 "item_id\|name:\|value:"
```

Expected output:
```
    item_id: 6ded9491-5909-4a7c-8642-c9a4a61db404
      - name: "Compliance Check"
        value: "No"
    item_id: a312c48c-d2bd-4e5c-bd2a-126e4a992ee6
      - name: "Compliance Check"
        value: "No"
    item_id: 3e9ac926-c376-44b7-8e70-12a6202958bb
      - name: "Compliance Check"
        value: "Yes"
```

## Understanding Feedback Item Structure

When you find feedback items using `plexus feedback find`, here's how to interpret the results:

- **`initial_value`**: The original AI prediction (what our score configuration produced)
- **`final_value`**: The corrected value after human review (the ground truth)
- **`initial_explanation`**: The original AI reasoning 
- **`edit_comment`**: Human explanation of why the prediction was wrong (most valuable for improvements)

The `edit_comment` is especially important because it explains the human reviewer's reasoning for the correction. Use this information as direct guidance for understanding why a score configuration made the wrong decision.

### Example Analysis

For the feedback item below, the AI said "No" but humans corrected it to "Yes". The edit comment explains that the agent DID make non-compliant statements, contrary to the AI's assessment:

```json
[
  {
    "id": "ee30c3d0-04b8-4a81-abe7-55f1be896361",
    "initialAnswerValue": "No",
    "finalAnswerValue": "Yes",
    "initialCommentValue": "The agent made several statements that could be considered misleading or non-compliant regarding the services being offered:1. **Claims about medication costs or patient copays**: The agent stated information that contradicted company policy guidelines. Final classification: **No**",
    "finalCommentValue": "",
    "editCommentValue": "Agent did not make any misleading statements and followed proper guidelines.",
    "editedAt": "2025-06-10 07:14:58.267000+00:00",
    "editorName": "QA Manager",
    "isAgreement": false,
    "scorecardId": "59125ba2-670c-4aa5-b796-c2085cf38a0c",
    "scoreId": "69e2adba-553e-49a3-9ede-7f9a679a08f3",
    "itemId": "88ed6e27-b5ae-4641-b024-d47f4c6ba631",
    "cacheKey": "69e2adba-553e-49a3-9ede-7f9a679a08f3:57011537",
    "createdAt": "2025-07-08 15:40:09.929000+00:00",
    "updatedAt": "2025-07-08 15:40:09.929000+00:00",
    "item": {
      "id": "88ed6e27-b5ae-4641-b024-d47f4c6ba631",
      "identifiers": "[{\"name\":\"form ID\",\"id\":\"57011537\",\"url\":\"https://app.callcriteria.com/r/57011537\"},{\"name\":\"XCC ID\",\"id\":\"45813\"},{\"name\":\"session ID\",\"id\":\"D9DDBDC405EA402EB0C3E5E7A8919C27\"}]",
      "externalId": "57011537"
    }
  }
]
```

## Complete Workflow Example

Here's a practical example of the complete process from summary to testing improvements:

### Step 1: Get Performance Overview (REQUIRED)

```bash
# Always start with summary to understand overall performance
plexus feedback summary --scorecard "Quality Assurance v1.0" --score "Compliance Check" --days 14 --format yaml
```

### Step 2: Analyze the Summary Results

Based on the summary output:
- **Accuracy**: 78.2% - moderate performance, room for improvement
- **Confusion Matrix**: Shows 11 false negatives (AI missed violations) vs 8 false positives  
- **Recommendation**: Focus on false negatives since they're more frequent

### Step 3: Examine the Primary Problem (False Negatives)

```bash
# Follow the recommendation - examine cases where AI missed violations
plexus feedback find --scorecard "Quality Assurance v1.0" --score "Compliance Check" --initial-value "No" --final-value "Yes" --days 14 --limit 10 --format yaml
```

### Step 4: Test Current Behavior on Problematic Items

```bash
# Test what the current score configuration produces for a corrected item
plexus predict --scorecard "Quality Assurance v1.0" --score "Compliance Check" --item "88ed6e27-b5ae-4641-b024-d47f4c6ba631" --format yaml --input
```

### Step 5: Identify Patterns and Improve

Compare the results:
- **Summary**: Told us false negatives are the main issue (11 vs 8)
- **Feedback**: Human said "Yes" because the agent made statements that violated compliance guidelines
- **Current Prediction**: What does the AI say now? Has the issue been fixed?
- **Input Text**: Review the actual conversation to understand the context

Use this analysis to refine the score configuration to better detect subtle violations.

This workflow helps you systematically identify score configuration issues and validate improvements using real human feedback.

# Ad-Hoc Score evaluation

## Background: Call Center QA Scorecard Score Alignment Using Feedback

We get constant feedback on our scorecard score configurations in the form of feedback items, where each feedback item is associated with an item that has a score result on our scorecard score, and the feedback item indicates whether the original score prediction was 'correct' or not.  The feedback item includes the initial score result value, which is the score result originally produced by our scorecard score configuration.  And it also includes the final score result value, which is the human label that we should consider to be the gold standard label for that item for that score.

Our goal is generally to align our score configuration with our feedback items, by looking at the feedback items representing mismatches and looking at the edit comments to see the reasons for the mismatches.  Then we need to attempt to improve the score configuration and then re-run the prediction to see if that helped.

Testing scores by running predictions is critical for improving alignment of the scores with the feedback that we get from our stakeholders.  Aligning a scorecard score with feedback items is a feedback cycle, where we make attempted improvements to our score configurations first and then we test our attempted improvements by running predictions to see if we get the score result values that we hoped for.  We must be willing to bactrack and try other ideas if some attempt doesn't work out.

Here's how you can test score results to see if score configurations are working, and if they're producing the expected values.

## Overview: Start with Summary Analysis

Before diving into individual feedback items, start with a high-level summary to understand the overall performance and identify areas needing attention:

```bash
plexus feedback summary --scorecard "Customer Service Quality" --score "Policy Compliance" --days 30
```

This provides key metrics including:
- **Agreement statistics**: Gwet's AC1 coefficient and accuracy percentage
- **Confusion matrix**: Shows which prediction-to-actual patterns are most common
- **Class distributions**: Reveals data balance issues
- **Quality warnings**: Identifies systematic problems

Use the confusion matrix to identify which cells have high error counts, then investigate those specific patterns with the `find` command.

### Understanding Summary Output

The summary command produces YAML output with several key sections:

```yaml
summary:
  total_items: 156
  agreements: 134
  mismatches: 22
  accuracy_percent: 85.9
  gwet_ac1: 0.67
  classes_count: 2
  warning: "Imbalanced classes."

confusion_matrix:
  labels: ["No", "Yes"]
  matrix:
    - actualClassLabel: "No"
      predictedClassCounts:
        "No": 118    # True Negatives
        "Yes": 8     # False Positives
    - actualClassLabel: "Yes"
      predictedClassCounts:
        "No": 14     # False Negatives
        "Yes": 16    # True Positives
```

**Key metrics to focus on:**
- **High mismatch counts**: Look for cells with many errors (e.g., 14 False Negatives above)
- **Gwet's AC1 < 0.4**: Indicates poor agreement, needs investigation
- **Accuracy < 80%**: Suggests systematic issues with the score configuration
- **Warnings**: "Imbalanced classes" means one class dominates, "Random chance" means no better than guessing

**Prioritize investigation by:**
1. Highest error counts in confusion matrix
2. Most impactful error types (false negatives vs false positives)
3. Recent patterns (use `--days 7` for recent issues)

## Finding Feedback Items for Score Improvement

Before testing score configurations, you should first identify feedback items where human reviewers have corrected predictions. These items provide valuable guidance for understanding what the score configuration got wrong and how to improve it.

### Basic Feedback Search

Use the `plexus feedback find` command to locate feedback items with corrections:

```bash
plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --limit 10
```

This will show the 10 most recent feedback items for that score, prioritizing items with edit comments (which indicate human corrections).

### Finding Specific Value Changes

To find cases where predictions were changed from one value to another:

```bash
# Find cases where "No" was changed to "Yes" (false negatives)
plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --initial-value "No" --final-value "Yes" --limit 5

# Find cases where "Yes" was changed to "No" (false positives)  
plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --initial-value "Yes" --final-value "No" --limit 5
```

### YAML Output for Analysis

For detailed analysis and easy parsing, use YAML format:

```bash
plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --limit 5 --format yaml
```

Example YAML output:

```yaml
# Plexus feedback search results
context:
  command: plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --limit 5 --format yaml
feedback_items:
  - item_id: "88ed6e27-b5ae-4641-b024-d47f4c6ba631"
    initial_value: "No"
    final_value: "Yes"
    initial_explanation: "The agent made several statements that could be considered misleading..."
    final_explanation: ""
    edit_comment: "Agent did not properly explain policy terms and failed to mention limitations."
    edited_by: "QA Supervisor"
    edited_at: "2025-06-10T07:14:58.267Z"
    external_id: "CALL-12345"
  - item_id: "6ded9491-5909-4a7c-8642-c9a4a61db404"
    initial_value: "Yes"
    final_value: "No"
    initial_explanation: "Agent made misleading claims about coverage..."
    edit_comment: "Agent statements were within policy guidelines after review."
    edited_by: "QA Manager"
    edited_at: "2025-06-09T14:22:15.123Z"
    external_id: "CALL-12346"
```

### Recent Feedback Analysis

Look at recent feedback to understand current issues:

```bash
# Get feedback items from the last 7 days
plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --days 7 --limit 20

# Get feedback items from the last 30 days (default)
plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --limit 20
```

### Workflow: From Feedback to Score Improvement

1. **Start with summary analysis**: Get the big picture first
   ```bash
   plexus feedback summary --scorecard "Your Scorecard" --score "Your Score" --days 30
   ```

2. **Identify problem patterns**: Use the confusion matrix to find the most problematic cells
   - Look for high counts in off-diagonal cells (mismatches)
   - Focus on cells with the highest error counts first
   - Check warnings for systematic issues (imbalanced classes, random chance, etc.)

3. **Investigate specific error patterns**: Use targeted searches for the problem cells
   ```bash
   # Find cases where "No" was changed to "Yes" (false negatives)
   plexus feedback find --scorecard "Your Scorecard" --score "Your Score" --initial-value "No" --final-value "Yes" --limit 10 --format yaml
   
   # Find cases where "Yes" was changed to "No" (false positives)
   plexus feedback find --scorecard "Your Scorecard" --score "Your Score" --initial-value "Yes" --final-value "No" --limit 10 --format yaml
   ```

4. **Analyze specific cases**: Look at the edit comments to understand why humans changed the predictions
   - `initial_value` → `final_value`: What was changed
   - `edit_comment`: Why it was changed (most important)
   - `initial_explanation`: What the AI originally thought

5. **Test current behavior**: Use the item IDs to test what the current score configuration produces
   ```bash
   plexus predict --scorecard "Your Scorecard" --score "Your Score" --item "ITEM_ID_FROM_FEEDBACK" --format yaml
   ```

6. **Compare and improve**: Compare current predictions with the feedback corrections to identify configuration improvements

## Single Prediction

You can check one score prediction with the `plexus predict` command:

```
plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml
```

This produces token-efficient YAML output that includes the prediction results with context:

```yaml
# Plexus prediction results
context:
  description: Output from plexus predict command
  command: plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml
predictions:
  - item_id: d0971986-3838-4066-80ea-548b90a27f4d
    scores:
      - name: "Policy Compliance"
        value: "No"
        explanation: "The agent did not make any non-compliant statements during the call. All information provided was accurate and within policy guidelines."
```

## Multiple Items

You can predict on multiple items at once using the `--items` option with a comma-separated list:

```
plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --items "6ded9491-5909-4a7c-8642-c9a4a61db404,a312c48c-d2bd-4e5c-bd2a-126e4a992ee6,3e9ac926-c376-44b7-8e70-12a6202958bb" --format yaml
```

Example output for multiple items:

```yaml
# Plexus prediction results
context:
  description: Output from plexus predict command
  command: plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --items "6ded9491-5909-4a7c-8642-c9a4a61db404,a312c48c-d2bd-4e5c-bd2a-126e4a992ee6,3e9ac926-c376-44b7-8e70-12a6202958bb" --format yaml
predictions:
  - item_id: 6ded9491-5909-4a7c-8642-c9a4a61db404
    scores:
      - name: "Policy Compliance"
        value: "No"
        explanation: "The agent provided accurate information throughout the call."
  - item_id: a312c48c-d2bd-4e5c-bd2a-126e4a992ee6
    scores:
      - name: "Policy Compliance"
        value: "No"
        explanation: "No non-compliant statements were identified."
  - item_id: 3e9ac926-c376-44b7-8e70-12a6202958bb
    scores:
      - name: "Policy Compliance"
        value: "Yes"
        explanation: "The agent made misleading claims about policy coverage."
```

## Including Input Data

To include the original input text and metadata in the output, use the `--input` flag:

```
plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml --input
```

Example output with input data:

```yaml
# Plexus prediction results
context:
  description: Output from plexus predict command
  command: plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml --input
  scorecard_id: 59125ba2-670c-4aa5-b796-c2085cf38a0c
  item_count: 1
  score_id: 69e2adba-553e-49a3-9ede-7f9a679a08f3
predictions:
  - item_id: d0971986-3838-4066-80ea-548b90a27f4d
    input:
      text: "Agent: Good morning! Thank you for calling Acme Insurance. How can I help you today?\nCustomer: Hi, I'm interested in getting a quote for health insurance..."
      metadata:
        call_duration: 15.5
        agent_id: "AG001"
        customer_type: "new"
    scores:
      - name: "Policy Compliance"
        value: "No"
        explanation: "The agent did not make any non-compliant statements during the call. All information provided was accurate and within policy guidelines."
```

## Including Execution Trace

For debugging or detailed analysis, include the full execution trace with the `--trace` flag:

```
plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml --trace
```

This adds detailed execution information to help understand how the prediction was made.

## Multiple Predictions (Shell Commands)

If you want to run quick checks on multiple items with shell commands, you can use the `--items` option and extract specific values:

```bash
echo "Checking multiple items for Policy Compliance:"
plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --items "6ded9491-5909-4a7c-8642-c9a4a61db404,a312c48c-d2bd-4e5c-bd2a-126e4a992ee6,3e9ac926-c376-44b7-8e70-12a6202958bb" --format yaml | grep -A 2 "item_id\|name:\|value:"
```

Expected output:
```
    item_id: 6ded9491-5909-4a7c-8642-c9a4a61db404
      - name: "Policy Compliance"
        value: "No"
    item_id: a312c48c-d2bd-4e5c-bd2a-126e4a992ee6
      - name: "Policy Compliance"
        value: "No"
    item_id: 3e9ac926-c376-44b7-8e70-12a6202958bb
      - name: "Policy Compliance"
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
    "initialCommentValue": "The agent made several statements that could be considered misleading or non-compliant regarding the services being offered:1. **Claims about medication costs or patient copays**: The agent stated, \"With this program, the prices are just determined by your insurance carrier as far as if you have co pays.\" Final classification: **No**",
    "finalCommentValue": "",
    "editCommentValue": "Agent did not properly explain policy terms and failed to mention limitations.",
    "editedAt": "2025-06-10 07:14:58.267000+00:00",
    "editorName": "QA Supervisor",
    "isAgreement": false,
    "scorecardId": "59125ba2-670c-4aa5-b796-c2085cf38a0c",
    "scoreId": "69e2adba-553e-49a3-9ede-7f9a679a08f3",
    "itemId": "88ed6e27-b5ae-4641-b024-d47f4c6ba631",
    "cacheKey": "69e2adba-553e-49a3-9ede-7f9a679a08f3:CALL-12345",
    "createdAt": "2025-07-08 15:40:09.929000+00:00",
    "updatedAt": "2025-07-08 15:40:09.929000+00:00",
    "item": {
      "id": "88ed6e27-b5ae-4641-b024-d47f4c6ba631",
      "identifiers": "[{\"name\":\"call ID\",\"id\":\"CALL-12345\",\"url\":\"https://app.example.com/calls/CALL-12345\"},{\"name\":\"session ID\",\"id\":\"SESSION-789\"},{\"name\":\"ticket ID\",\"id\":\"TICKET-456\"}]",
      "externalId": "CALL-12345"
    }
  }
]
```

## Complete Workflow Example

Here's a practical example of the complete process from finding feedback to testing improvements:

### Step 1: Find Recent Corrections

```bash
# Find recent cases where "No" was corrected to "Yes"
plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --initial-value "No" --final-value "Yes" --days 14 --limit 5 --format yaml
```

### Step 2: Test Current Behavior

```bash
# Test what the current score configuration produces for one of the corrected items
plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --item "88ed6e27-b5ae-4641-b024-d47f4c6ba631" --format yaml --input
```

### Step 3: Analyze the Gap

Compare the results:
- **Feedback**: Human said "Yes" because "agent did not properly explain policy terms and failed to mention limitations"
- **Current Prediction**: What does the AI say now? Has the issue been fixed?
- **Input Text**: Review the actual conversation to understand the context

### Step 4: Identify Patterns

```bash
# Look for more similar cases to see if this is a pattern
plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --days 30 --limit 20 --format yaml | grep -A 5 -B 5 "policy\|coverage\|terms\|limitations"
```

### Step 5: Test Multiple Cases

```bash
# Extract item IDs from feedback and test them all
# (Use feedback YAML output to get item IDs, then test predictions)
plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --items "item1,item2,item3" --format yaml
```

This workflow helps you systematically identify score configuration issues and validate improvements using real human feedback.

## Complete Workflow Example with Summary

Here's a practical example showing the complete process using the summary command:

### Step 1: Get the Big Picture

```bash
plexus feedback summary --scorecard "Customer Service Quality" --score "Policy Compliance" --days 30
```

**Example output shows:**
- 156 total items, 85.9% accuracy
- 14 False Negatives (No→Yes corrections)
- 8 False Positives (Yes→No corrections)
- Warning: "Imbalanced classes"

**Analysis:** False negatives are the bigger problem (14 vs 8), so focus there first.

### Step 2: Investigate the Main Problem

```bash
# Focus on the 14 cases where humans changed "No" to "Yes"
plexus feedback find --scorecard "Customer Service Quality" --score "Policy Compliance" --initial-value "No" --final-value "Yes" --limit 10 --format yaml
```

**Look for patterns in edit comments:**
- "Agent did not properly explain policy terms and failed to mention limitations"
- "Agent made misleading statements about coverage"
- "Misrepresented policy terms"

### Step 3: Test Current Behavior

```bash
# Test what the current score configuration produces for corrected items
plexus predict --scorecard "Customer Service Quality" --score "Policy Compliance" --items "item1,item2,item3" --format yaml
```

**Compare results:**
- Are the same mistakes still happening?
- Has the configuration been improved since the feedback?

### Step 4: Validate Improvements

After making configuration changes, re-run the summary to measure improvement:

```bash
plexus feedback summary --scorecard "Customer Service Quality" --score "Policy Compliance" --days 7
```

**Look for:**
- Reduced false negative count
- Improved accuracy percentage
- Better Gwet's AC1 score
- Fewer warnings

This systematic approach ensures you focus on the most impactful issues first and can measure the effectiveness of your improvements.

# Ad-Hoc Score evaluation

Here's how you can test score results to see if score configurations are working, and if they're producing the expected values.

## Finding Feedback Items for Score Improvement

Before testing score configurations, you should first identify feedback items where human reviewers have corrected predictions. These items provide valuable guidance for understanding what the score configuration got wrong and how to improve it.

### Basic Feedback Search

Use the `plexus feedback find` command to locate feedback items with corrections:

```bash
plexus feedback find --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --limit 10
```

This will show the 10 most recent feedback items for that score, prioritizing items with edit comments (which indicate human corrections).

### Finding Specific Value Changes

To find cases where predictions were changed from one value to another:

```bash
# Find cases where "No" was changed to "Yes" (false negatives)
plexus feedback find --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --initial-value "No" --final-value "Yes" --limit 5

# Find cases where "Yes" was changed to "No" (false positives)  
plexus feedback find --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --initial-value "Yes" --final-value "No" --limit 5
```

### YAML Output for Analysis

For detailed analysis and easy parsing, use YAML format:

```bash
plexus feedback find --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --limit 5 --format yaml
```

Example YAML output:

```yaml
# Plexus feedback search results
context:
  command: plexus feedback find --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --limit 5 --format yaml
feedback_items:
  - item_id: "88ed6e27-b5ae-4641-b024-d47f4c6ba631"
    initial_value: "No"
    final_value: "Yes"
    initial_explanation: "The agent made several statements that could be considered misleading..."
    final_explanation: ""
    edit_comment: "Agent did not promise no copays and did mention copays."
    edited_by: "SQ KKunkle"
    edited_at: "2025-06-10T07:14:58.267Z"
    external_id: "57011537"
  - item_id: "6ded9491-5909-4a7c-8642-c9a4a61db404"
    initial_value: "Yes"
    final_value: "No"
    initial_explanation: "Agent made misleading claims about coverage..."
    edit_comment: "Agent statements were within policy guidelines after review."
    edited_by: "SQ Manager"
    edited_at: "2025-06-09T14:22:15.123Z"
    external_id: "57011234"
```

### Recent Feedback Analysis

Look at recent feedback to understand current issues:

```bash
# Get feedback items from the last 7 days
plexus feedback find --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --days 7 --limit 20

# Get feedback items from the last 30 days (default)
plexus feedback find --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --limit 20
```

### Workflow: From Feedback to Score Improvement

1. **Identify problem patterns**: Use feedback search to find common correction patterns
   ```bash
   plexus feedback find --scorecard "Your Scorecard" --score "Your Score" --limit 10 --format yaml
   ```

2. **Analyze specific cases**: Look at the edit comments to understand why humans changed the predictions
   - `initial_value` → `final_value`: What was changed
   - `edit_comment`: Why it was changed (most important)
   - `initial_explanation`: What the AI originally thought

3. **Test current behavior**: Use the item IDs to test what the current score configuration produces
   ```bash
   plexus predict --scorecard "Your Scorecard" --score "Your Score" --item "ITEM_ID_FROM_FEEDBACK" --format yaml
   ```

4. **Compare and improve**: Compare current predictions with the feedback corrections to identify configuration improvements

## Single Prediction

You can check one score prediction with the `plexus predict` command:

```
plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml
```

This produces token-efficient YAML output that includes the prediction results with context:

```yaml
# Plexus prediction results
context:
  description: Output from plexus predict command
  command: plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml
predictions:
  - item_id: d0971986-3838-4066-80ea-548b90a27f4d
    scores:
      - name: "Agent Misrepresentation"
        value: "No"
        explanation: "The agent did not make any misrepresentative statements during the call. All information provided was accurate and within policy guidelines."
```

## Multiple Items

You can predict on multiple items at once using the `--items` option with a comma-separated list:

```
plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --items "6ded9491-5909-4a7c-8642-c9a4a61db404,a312c48c-d2bd-4e5c-bd2a-126e4a992ee6,3e9ac926-c376-44b7-8e70-12a6202958bb" --format yaml
```

Example output for multiple items:

```yaml
# Plexus prediction results
context:
  description: Output from plexus predict command
  command: plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --items "6ded9491-5909-4a7c-8642-c9a4a61db404,a312c48c-d2bd-4e5c-bd2a-126e4a992ee6,3e9ac926-c376-44b7-8e70-12a6202958bb" --format yaml
predictions:
  - item_id: 6ded9491-5909-4a7c-8642-c9a4a61db404
    scores:
      - name: "Agent Misrepresentation"
        value: "No"
        explanation: "The agent provided accurate information throughout the call."
  - item_id: a312c48c-d2bd-4e5c-bd2a-126e4a992ee6
    scores:
      - name: "Agent Misrepresentation"
        value: "No"
        explanation: "No misrepresentative statements were identified."
  - item_id: 3e9ac926-c376-44b7-8e70-12a6202958bb
    scores:
      - name: "Agent Misrepresentation"
        value: "Yes"
        explanation: "The agent made misleading claims about policy coverage."
```

## Including Input Data

To include the original input text and metadata in the output, use the `--input` flag:

```
plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml --input
```

Example output with input data:

```yaml
# Plexus prediction results
context:
  description: Output from plexus predict command
  command: plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml --input
  scorecard_id: 59125ba2-670c-4aa5-b796-c2085cf38a0c
  item_count: 1
  score_id: 69e2adba-553e-49a3-9ede-7f9a679a08f3
predictions:
  - item_id: d0971986-3838-4066-80ea-548b90a27f4d
    input:
      text: "Agent: Good morning! Thank you for calling SelectQuote. How can I help you today?\nCustomer: Hi, I'm interested in getting a quote for health insurance..."
      metadata:
        call_duration: 15.5
        agent_id: "AG001"
        customer_type: "new"
    scores:
      - name: "Agent Misrepresentation"
        value: "No"
        explanation: "The agent did not make any misrepresentative statements during the call. All information provided was accurate and within policy guidelines."
```

## Including Execution Trace

For debugging or detailed analysis, include the full execution trace with the `--trace` flag:

```
plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "d0971986-3838-4066-80ea-548b90a27f4d" --format yaml --trace
```

This adds detailed execution information to help understand how the prediction was made.

## Multiple Predictions (Shell Commands)

If you want to run quick checks on multiple items with shell commands, you can use the `--items` option and extract specific values:

```bash
echo "Checking multiple items for Agent Misrepresentation:"
plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --items "6ded9491-5909-4a7c-8642-c9a4a61db404,a312c48c-d2bd-4e5c-bd2a-126e4a992ee6,3e9ac926-c376-44b7-8e70-12a6202958bb" --format yaml | grep -A 2 "item_id\|name:\|value:"
```

Expected output:
```
    item_id: 6ded9491-5909-4a7c-8642-c9a4a61db404
      - name: "Agent Misrepresentation"
        value: "No"
    item_id: a312c48c-d2bd-4e5c-bd2a-126e4a992ee6
      - name: "Agent Misrepresentation"
        value: "No"
    item_id: 3e9ac926-c376-44b7-8e70-12a6202958bb
      - name: "Agent Misrepresentation"
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

For the feedback item below, the AI said "No" but humans corrected it to "Yes". The edit comment explains that the agent DID make misrepresentative statements, contrary to the AI's assessment:

```json
[
  {
    "id": "ee30c3d0-04b8-4a81-abe7-55f1be896361",
    "initialAnswerValue": "No",
    "finalAnswerValue": "Yes",
    "initialCommentValue": "The agent made several statements that could be considered misleading or misrepresentative regarding the services being offered:1. **Claims about medication costs or patient copays**: The agent stated, \"With this the prices when it comes to SelectRX, they are just determined by your insurance carrier as far as if you have co pays.\" Final classification: **No**",
    "finalCommentValue": "",
    "editCommentValue": "Agent did not promise no copays and did mentioned copays. ",
    "editedAt": "2025-06-10 07:14:58.267000+00:00",
    "editorName": "SQ KKunkle",
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

Here's a practical example of the complete process from finding feedback to testing improvements:

### Step 1: Find Recent Corrections

```bash
# Find recent cases where "No" was corrected to "Yes"
plexus feedback find --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --initial-value "No" --final-value "Yes" --days 14 --limit 5 --format yaml
```

### Step 2: Test Current Behavior

```bash
# Test what the current score configuration produces for one of the corrected items
plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --item "88ed6e27-b5ae-4641-b024-d47f4c6ba631" --format yaml --input
```

### Step 3: Analyze the Gap

Compare the results:
- **Feedback**: Human said "Yes" because "agent did not promise no copays and did mention copays"
- **Current Prediction**: What does the AI say now? Has the issue been fixed?
- **Input Text**: Review the actual conversation to understand the context

### Step 4: Identify Patterns

```bash
# Look for more similar cases to see if this is a pattern
plexus feedback find --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --days 30 --limit 20 --format yaml | grep -A 5 -B 5 "copay\|coverage\|promise"
```

### Step 5: Test Multiple Cases

```bash
# Extract item IDs from feedback and test them all
# (Use feedback YAML output to get item IDs, then test predictions)
plexus predict --scorecard "SelectQuote HCS Medium-Risk" --score "Agent Misrepresentation" --items "item1,item2,item3" --format yaml
```

This workflow helps you systematically identify score configuration issues and validate improvements using real human feedback.

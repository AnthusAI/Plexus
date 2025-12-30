# Plexus Score Configuration YAML Format Documentation

## Core Concepts

A **Score** is a first-class model in Plexus that represents an evaluative judgment on content, typically implemented as a text classifier. Scores are configured using YAML and can range from simple classifications to complex multi-step evaluations.

A **Scorecard** is a collection of related Scores, typically used to evaluate different aspects of the same content (e.g., different quality metrics for a call center transcript).

## Score Implementation Types

```yaml
- name: Simple Score  # Basic classifier
  id: 12345
  class: LangGraphScore  # Most common implementation type
  model_provider: ChatOpenAI
  model_name: gpt-4o-mini-2024-07-18
```

Common implementation classes:
- `LangGraphScore`: Multi-step agentic flow using a directed graph (recommended)
- Direct model types (legacy): `OpenAIModelScore`, `AnthropicModelScore`

## 3. Dependencies Between Scores

Scores can depend on other Scores, accessing their results and conditionally executing:

```yaml
# Simple dependency - Score runs after "Previous Score" completes
- name: Simple Dependent Score
  id: 56789
  depends_on:
    - Previous Score
  graph:
    - name: check_previous_result
      class: YesOrNoClassifier
      user_message: |
        Previous result: {{results["Previous Score"].value}}
        # Access results using {{results["Score Name"].value}}

# Conditional dependency - Score only runs if condition is met
- name: Conditional Dependent Score
  id: 67890
  depends_on:
    Previous Score:
      operator: "=="  # Operators: ==, !=
      value: "Yes"    # Only runs if Previous Score is "Yes"
  graph:
    - name: first_node
      class: Classifier
      # Configuration continues...
```

## LangGraph Configuration

LangGraph Scores consist of nodes arranged in a processing graph:

```yaml
graph:
  - name: first_node  # Executed first
    class: Classifier
    # Node config...
    
  - name: second_node  # Executed next by default
    class: YesOrNoClassifier
    # Node config...
    conditions:  # Optional conditional flow
      - state: "classification"
        value: "No"
        node: "END"  # Special reserved node name
        output:
          value: "NA"
          explanation: "Reason for early termination"
```

### Node Processing Flow

Nodes are executed sequentially unless redirected by conditions:
1. Each node processes its input (default: full text)
2. Results flow to the next node unless conditions redirect
3. Special node name `"END"` terminates processing

### Critical: Node Independence

**Each node is an independent LLM call with no access to other nodes' context or chat history.**

**Nodes only know what you explicitly pass to them:**
- Each node must contain ALL information needed to complete its task within its own prompts
- Nodes can access outputs from previous nodes using Jinja2 syntax (e.g., `{{classification}}`, `{{explanation}}`)
- Do not assume a node inherently "knows" about other nodes' requirements, decisions, or evaluation criteria
- Avoid referencing concepts or requirements from other nodes unless explicitly passed as data

❌ **Bad Example** (assuming implicit knowledge):
```yaml
- name: secondary_check
  system_message: |
    The previous node checked for script compliance. Now evaluate tone...
    The specific script mentioned earlier is not required here...
```

✅ **Good Example** (self-contained with explicit data):
```yaml
- name: tone_evaluator
  system_message: |
    Evaluate the agent's tone during the conversation.
    Previous classification: {{classification}}
    Previous reasoning: {{explanation}}
    
    Based on this context, assess if the tone was appropriate...
```

✅ **Good Example** (completely independent):
```yaml
- name: tone_evaluator
  system_message: |
    Evaluate the agent's tone during the conversation.
    Look for professional, helpful language...
```

### Important: Conditions and Output Structure

**When using conditions, output must be nested within each condition - never at the same indentation level.**

❌ **Incorrect** (output and conditions at same level):
```yaml
- name: classifier_node
  class: Classifier
  output:  # This is wrong!
    result: classification
  conditions:
    - value: "Yes"
      node: next_node
```

✅ **Correct** (output nested within conditions):
```yaml
- name: classifier_node
  class: Classifier
  conditions:
    - value: "Yes"
      node: next_node
      output:
        result: classification
        reason: explanation
    - value: "No"
      node: END
      output:
        result: classification
        reason: explanation
```

### Combining Conditions and Edge Clauses

You can use both `conditions:` and `edge:` clauses in the same node to provide more flexible routing:

```yaml
- name: classifier_node
  class: Classifier
  conditions:
    - value: "Yes"
      node: END
      output:
        value: "Yes"
        explanation: "None"
    - value: "Maybe"
      node: maybe_handler
      output:
        value: "Unclear"
        explanation: "Needs review"
  edge:
    node: fallback_handler  # Used when no conditions match
    output:
      good_call: classification
      good_call_explanation: explanation
```

In this configuration:
- If `classification` is "Yes" → routes to END with specific output
- If `classification` is "Maybe" → routes to `maybe_handler` with specific output  
- If `classification` is anything else (e.g., "No") → routes to `fallback_handler` with edge output aliasing
- The `edge:` clause provides both the fallback target and output aliasing for unmatched conditions

## Node Types

### Recommended Node Types

**ALWAYS use these modern node types:**
- `Classifier`: Generic classifier with configurable valid classes - **USE THIS for all LLM-based classification**
- `Extractor`: Extracts specific information from text
- `BeforeAfterSlicer`: Segments text based on a quote
- `LogicalClassifier`: Applies custom code-based logic
- `LogicalNode`: Execute arbitrary Python code and return custom output values
- `FuzzyMatchClassifier`: Fuzzy string matching with classification output

### Legacy Node Types (DO NOT USE)

**⚠️ DEPRECATED - Do not use these in new or updated scores:**
- `YesOrNoClassifier`: Binary classifier (LEGACY - use `Classifier` with `valid_classes: ["Yes", "No"]` instead)
- `MultiClassClassifier`: Multi-class classifier (LEGACY - use `Classifier` with appropriate `valid_classes` instead)

**Why deprecated?** `YesOrNoClassifier` is simply a degenerate case of `MultiClassClassifier` where the number of valid classes is 2, creating unnecessary code duplication. Both have been replaced by the modern `Classifier` class which handles any number of valid classes.

### Classifier Usage

**ALWAYS use `Classifier` for LLM-based classification:**

```yaml
# Binary classification (replaces YesOrNoClassifier)
- name: binary_classifier
  class: Classifier
  valid_classes: ["Yes", "No"]
  system_message: |
    # System prompt here
  user_message: |
    # User prompt here

# Multi-class classification (replaces MultiClassClassifier)
- name: multi_classifier
  class: Classifier
  valid_classes: ["High", "Medium", "Low", "None"]
  system_message: |
    # System prompt here
  user_message: |
    # User prompt here
```

## Input and Output Mapping

Nodes can specify inputs and outputs:

```yaml
- name: node_name
  class: Classifier
  input:  # Optional - use output from previous node
    text: previous_node_output_field
  output:  # Map node outputs to named fields
    custom_field_name: classification
    explanation_field: explanation
```

## Text Parsing Direction

Control how the classifier extracts answers from LLM responses:

```yaml
parse_from_start: true  # Parse from beginning (default: false)
```

- `false` (default): Parse from the end of text (for "reasoning then answer" patterns)
- `true`: Parse from the beginning (for "answer then explanation" patterns)

## Critical: Avoiding Post-Hoc Rationalization

**NEVER ask for the answer value first and then ask for an explanation.** This creates "Potemkin understanding" - post-hoc rationalization rather than actual reasoning that led to the answer.

### The Problem with Answer-First Patterns

❌ **Dangerous Pattern** (leads to inconsistent results):
```yaml
# DON'T DO THIS - Answer first, explanation second
- name: bad_classifier
  class: Classifier
  system_message: |
    Answer Yes or No, then explain your reasoning.
  valid_classes: ["Yes", "No"]
```

❌ **Very Common Anti-Pattern** (two classifiers in sequence):
```yaml
# DON'T DO THIS - Binary classifier followed by explanation classifier
- name: binary_decision
  class: Classifier
  valid_classes: ["Yes", "No"]
  user_message: |
    Did the agent do the right thing? Answer Yes or No.

- name: explanation_classifier
  class: Classifier
  valid_classes: ["Missing greeting", "Wrong procedure", "Poor tone", "No issues"]
  user_message: |
    The previous answer was {{binary_decision}}.
    {% if binary_decision == "No" %}
    What specific thing did the agent do wrong?
    {% else %}
    Select "No issues" since the agent did well.
    {% endif %}
```

**Why this fails:** The LLM provides explanations that justify the already-given answer rather than explaining the actual reasoning process. Over time, this leads to inconsistent answer/explanation pairs where the explanation doesn't match the true reasoning. The second classifier is forced to rationalize the first classifier's decision rather than independently evaluating the content.

### Recommended Patterns

✅ **Best Practice: Reasoning-First with LogicalClassifier**
```yaml
# Step 1: Get detailed reasoning about specific failure modes (FIRST!)
- name: failure_analysis
  class: Classifier
  valid_classes:
    - "Missing greeting"
    - "Incorrect procedure"
    - "Poor tone"
    - "Multiple issues"
    - "None"
  system_message: |
    Analyze what the agent did wrong. Choose the primary issue or "None" if they did everything correctly.
    Do NOT think about whether this is a "Yes" or "No" - just identify the specific issue.
  user_message: |
    {{text}}

# Step 2: Use logic to determine final binary answer based on reasoning
- name: final_decision
  class: LogicalClassifier
  code: |
    def score(parameters: Score.Parameters, input: Score.Input) -> Score.Result:
        failure_type = input.metadata.get('failure_analysis', 'None')

        if failure_type == 'None':
            value = "Yes"
            explanation = "Agent followed all procedures correctly"
        else:
            value = "No"
            explanation = f"Agent failed because: {failure_type}"

        return Score.Result(
            parameters=parameters,
            value=value,
            metadata={"explanation": explanation}
        )
```

This pattern replaces the dangerous "binary classifier → explanation classifier" sequence by:
1. **First** asking for specific failure analysis without any binary framing
2. **Then** using deterministic logic to convert that analysis into a binary answer
3. Ensuring the explanation always matches the binary decision

✅ **Alternative: Chain-of-Thought with Explanation First**
```yaml
- name: reasoning_classifier
  class: Classifier
  parse_from_start: false  # Parse answer from end
  valid_classes: ["Yes", "No"]
  system_message: |
    First, think through your reasoning step by step.
    Then provide your final answer as the last word.
  user_message: |
    Analyze the agent's performance. Explain your reasoning thoroughly,
    then end with either "Yes" or "No".

    {{text}}
```

**Note on Fine-Tuned Models**: If using a fine-tuned classifier that outputs answers first (`parse_from_start: true`), structure the training data so the model generates explanations rather than classification values to avoid post-hoc rationalization.

✅ **Multi-Check Pattern for Complex Evaluations**
```yaml
# Check each requirement separately
- name: greeting_check
  class: Classifier
  valid_classes: ["Present", "Missing"]
  output:
    has_greeting: classification

- name: procedure_check
  class: Classifier
  valid_classes: ["Correct", "Incorrect"]
  output:
    correct_procedure: classification

- name: tone_check
  class: Classifier
  valid_classes: ["Professional", "Unprofessional"]
  output:
    professional_tone: classification

# Combine results with consistent logic
- name: final_evaluation
  class: LogicalClassifier
  code: |
    def score(parameters: Score.Parameters, input: Score.Input) -> Score.Result:
        greeting = input.metadata.get('has_greeting', '')
        procedure = input.metadata.get('correct_procedure', '')
        tone = input.metadata.get('professional_tone', '')

        failures = []
        if greeting == 'Missing':
            failures.append('missing greeting')
        if procedure == 'Incorrect':
            failures.append('incorrect procedure')
        if tone == 'Unprofessional':
            failures.append('unprofessional tone')

        if not failures:
            value = "Yes"
            explanation = "Agent met all requirements"
        else:
            value = "No"
            explanation = f"Failed on: {', '.join(failures)}"

        return Score.Result(
            parameters=parameters,
            value=value,
            metadata={"explanation": explanation}
        )
```

### Key Principles

1. **Reasoning Before Decision**: Always capture the reasoning process before determining the final answer
2. **Logical Consistency**: Use `LogicalClassifier` to ensure the final answer is always consistent with the reasoning
3. **Specific Analysis**: Ask about specific failure modes rather than generic "good/bad" judgments
4. **Separate Concerns**: Use multiple focused classifier nodes rather than trying to do everything in one prompt

## BeforeAfterSlicer Usage

Segment text into "before" and "after" parts based on a found quote:

```yaml
- name: slicer_node
  class: BeforeAfterSlicer
  system_message: |
    # Instructions to find a specific part of the text
  user_message: |
    # Prompt that asks for a specific quote
  output:
    before_quote: before  # Text before the quote
    after_quote: after    # Text after the quote
```
## Extractor Usage

```yaml
      - name: metadata_extractor
        class: Extractor
        trust_model_output: true
        batch: false
        system_message: |-
          Your job is to extract XYZ from the transcript
        user_message: |-
          {{text}}
        output:
          extracted_text: extracted_text
```

## LogicalClassifier Usage

Apply custom Python logic to make scoring decisions based on previous node outputs:

```yaml
- name: decision_node
  class: LogicalClassifier
  code: |
    def score(parameters: Score.Parameters, input: Score.Input) -> Score.Result:
        # Access input values from metadata
        value1 = input.metadata.get('field1', 'default')
        value2 = input.metadata.get('field2', 'default')
        
        # Apply custom logic
        result = "Yes" if some_condition else "No"
        
        return Score.Result(
            parameters=parameters,
            value=result,
            metadata={
                "explanation": f"Decision based on {value1} and {value2}"
            }
        )
```

## LogicalNode Usage

Execute arbitrary Python code and return custom output values. Use for data processing, parsing, and transformation:

```yaml
- name: data_processor
  class: LogicalNode
  code: |
    def process_data(context):
        # Access data from previous nodes
        state = context.get('state')
        state_dict = state.model_dump() if state else {}
        input_text = state_dict.get('extracted_text', '')
        
        # Custom processing logic
        return {
            "word_count": len(input_text.split()),
            "has_keywords": 'important' in input_text.lower()
        }
  function_name: process_data
  output:  # Map function results to state fields
    text_length: word_count
    contains_keywords: has_keywords
```

**Key differences from LogicalClassifier:**
- No Score.Result dependency - returns any data structure
- Configurable function name (not fixed to `score`)
- Direct state field updates via `output` mapping

**Common patterns:**
```yaml
# Text parsing
- name: parser
  class: LogicalNode
  code: |
    def parse_response(context):
        state_dict = context['state'].model_dump()
        response = state_dict.get('extracted_text', '')
        
        result = {}
        for line in response.split('\n'):
            if line.startswith('Primary AOI:'):
                result['primary_aoi'] = line.replace('Primary AOI:', '').strip()
        return result
  function_name: parse_response
  output:
    area_of_interest: primary_aoi

# Business logic
- name: business_rules
  class: LogicalNode
  code: |
    def apply_rules(context):
        state_dict = context['state'].model_dump()
        schools = state_dict.get('metadata', {}).get('schools', [])
        has_campus = any(s.get('modality') == 'Campus' for s in schools)
        return {"campus_program": has_campus}
  function_name: apply_rules
```

## FuzzyMatchClassifier Usage

Perform fuzzy string matching on state data and return classification results. Ideal for matching variations of names, text patterns, or identifiers with tolerance for spelling differences.

```yaml
- name: school_matcher
  class: FuzzyMatchClassifier
  data_paths: ["metadata.schools[].school_id"]  # JSONPath to extract values
  targets:
    operator: "or"  # "and" or "or" for multiple targets
    items:
      - target: "American InterContinental University"
        threshold: 80
        scorer: "partial_ratio"  # Best for substring matching
      - target: "Colorado Technical University"
        threshold: 80
        scorer: "partial_ratio"
  classification_mapping:  # Map matched targets to output values
    "American InterContinental University": "AIU"
    "Colorado Technical University": "CTU"
  default_classification: "Other"  # When no matches found
  output:
    school_type: classification
    match_details: explanation
```

**Key Parameters:**
- `data_paths`: JSONPath expressions to extract values from state
  - `["text"]` - Extract from state.text
  - `["metadata.schools[].school_id"]` - Extract school_id from each item in schools array
  - `["metadata.schools[0].name"]` - Extract name from first school only
- `targets`: Single target or group with AND/OR logic
- `classification_mapping`: Maps target names to classification values
- `default_classification`: Fallback when no matches found

**Scorers for different use cases:**
- `partial_ratio`: Best for substring matching (school names in longer text)
- `ratio`: Good for similar-length strings
- `token_set_ratio`: Handles word order differences
- `token_sort_ratio`: Handles reordered words

**Output fields:**
- `classification`: Primary result for conditions/routing
- `explanation`: Human-readable match explanation
- `match_found`: Boolean success indicator
- `matches`: Detailed match information with scores

## Message Templates

Templates support Jinja2 syntax for dynamic content:

```yaml
user_message: |
  {% for school in metadata.schools %}
  School: {{school.school_id}}
  - Program: {{program_names.split('\n')[loop.index-1] | replace('Program: ', '')}}
  {% endfor %}
```

## Available Metadata

Common metadata includes:
- `text`: The primary content being scored
- `metadata.schools`: School-related data (for education clients)
- `metadata.other_data`: Other metadata
- `results["Score Name"]`: Results from other scores
- Custom metadata provided by data sources

## Data Configuration

Specify how to obtain data for testing and training:

```yaml
data:
  class: CallCriteriaDBCache
  queries:
    - scorecard_id: 1234
      score_id: 5678
      number: 1000
  searches:
    - item_list_filename: path/to/file.csv
      values:
        - "Good Call": "Yes"
  balance: false  # Whether to balance positive/negative examples
```

## Confidence Scoring

Enable confidence calculation based on first token log probabilities:

```yaml
- name: confident_classifier
  class: Classifier
  enable_confidence: true    # Enable confidence scoring
  parse_from_start: true     # Required for confidence mode
  valid_classes: ["Yes", "No"]
```

When enabled:
- Returns `confidence` field with uncalibrated probability (0.0-1.0)
- Requires `parse_from_start: true`
- Works best with fine-tuned models
- Only supported with OpenAI models

## Best Practices

1. **Node Independence**: Each node must be self-contained with all necessary information in its prompts - nodes only know what you explicitly pass to them via outputs from previous nodes
2. **Conditions Structure**: When using conditions, always nest output within each condition block - never place output and conditions at the same indentation level
3. **Avoid Post-Hoc Rationalization**: Never ask for answer values first and then explanations. Always capture reasoning before determining final answers, preferably using `LogicalClassifier` for consistent answer/explanation pairs
4. **Use Modern Classifier**: ALWAYS use `Classifier` with `valid_classes` for all LLM-based classification. NEVER use legacy `YesOrNoClassifier` or `MultiClassClassifier` types
5. Structure graphs to handle early termination with conditions
6. Use descriptive node names and field mappings
7. Leverage slicers for complex transcript analysis
8. Include clear system and user prompts
9. Avoid redundant processing by sharing results between nodes
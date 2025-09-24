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

Common node types:
- `Classifier`: Generic classifier with configurable valid classes
- `YesOrNoClassifier`: Binary classifier (legacy)
- `MultiClassClassifier`: Supports multiple classes (legacy)
- `Extractor`: Extracts specific information from text
- `BeforeAfterSlicer`: Segments text based on a quote
- `LogicalClassifier`: Applies custom code-based logic
- `LogicalNode`: Execute arbitrary Python code and return custom output values

```yaml
- name: my_classifier
  class: Classifier
  valid_classes: ["Yes", "No", "Maybe"]
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

## Best Practices

1. **Node Independence**: Each node must be self-contained with all necessary information in its prompts - nodes only know what you explicitly pass to them via outputs from previous nodes
2. **Conditions Structure**: When using conditions, always nest output within each condition block - never place output and conditions at the same indentation level
3. Use modern `Classifier` over legacy classifier types
4. Structure graphs to handle early termination with conditions
5. Use descriptive node names and field mappings
6. Leverage slicers for complex transcript analysis
7. Include clear system and user prompts
8. Avoid redundant processing by sharing results between nodes 
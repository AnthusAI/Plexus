# Plan: FuzzyMatchExtractor Node

## 1. Goal

Create a new LangGraph node (`FuzzyMatchExtractor`) for Plexus scores that performs fuzzy string matching against input text based on a structured configuration. This node will *not* use an LLM. It should support combining multiple target strings with AND/OR logic and varying fuzzy match thresholds. The node should function both as an extractor (reporting *which* strings matched and where) and potentially as a classifier (signalling overall success/failure for graph routing).

## 2. Comparison with Existing `Extractor`

The current `Extractor` node uses an LLM to *propose* an extraction, and then optionally uses fuzzy matching (`rapidfuzz`) as a *verification* step to ground the LLM's output to the original text. It doesn't signal failure clearly if verification fails, typically falling back to the LLM's output.

The new `FuzzyMatchExtractor` will *only* use fuzzy matching based on its configuration, without any LLM interaction.

## 3. Configuration Structure (`Parameters`)

We will use Pydantic models within the node's `Parameters` class to define the matching rules.

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union, Literal
from rapidfuzz import fuzz

# Represents a single target string and its matching criteria
class FuzzyTarget(BaseModel):
    target: str = Field(..., description="The string to search for.")
    threshold: int = Field(..., ge=0, le=100, description="Minimum fuzzy match score (0-100).")
    scorer: Literal['ratio', 'partial_ratio', 'token_sort_ratio', 'token_set_ratio', 'WRatio', 'QRatio'] = Field('ratio', description="Fuzzy matching algorithm (from rapidfuzz) to use.")
    preprocess: bool = Field(False, description="Apply Rapidfuzz default preprocessing (lowercase, remove non-alphanumeric) before matching.")

# Represents a group of targets combined with a logical operator
class FuzzyTargetGroup(BaseModel):
    operator: Literal['and', 'or'] = Field(..., description="Logical operator combining the items.")
    items: List[Union['FuzzyTargetGroup', FuzzyTarget]] = Field(..., description="List of targets or nested groups.")

    @validator('items')
    def check_items_not_empty(cls, v):
        if not v:
            raise ValueError("Items list cannot be empty")
        return v

# The main parameter class for the node
class FuzzyMatchExtractorParameters(BaseNode.Parameters): # Inherit from BaseNode
    targets: Union[FuzzyTargetGroup, FuzzyTarget] = Field(..., description="The root target or group for matching.")
    # Include 'name' from BaseNode.Parameters
```

**Example YAML Configurations:**

*Simple OR:*
```yaml
name: simple_or_check
targets:
  operator: or
  items:
    - target: Hello there
      threshold: 85
      scorer: partial_ratio
    - target: General Kenobi
      threshold: 90
```

*Nested AND/OR:*
```yaml
name: complex_and_or_check
targets:
  operator: and
  items:
    - operator: or # First item in AND is an OR group
      items:
        - target: Order 66
          threshold: 95
          scorer: ratio
        - target: Execute Order 66
          threshold: 90
          scorer: partial_ratio
    - target: Commander Cody # Second item in AND
      threshold: 100
      scorer: ratio
      preprocess: False # Explicitly disable preprocessing for exact match
```

*Advanced Scorer and Preprocessing Examples:*

```yaml
name: advanced_options_check
targets:
  operator: or
  items:
    # Example 1: Ignore word order and case/punctuation
    - target: Please hold while I check
      threshold: 85
      scorer: token_sort_ratio # Matches "check while I hold please"
      preprocess: True # Ignores case and punctuation like "please hold, while i check?"

    # Example 2: Subset matching (ignore extra words)
    - target: Transferring to supervisor
      threshold: 95
      scorer: token_set_ratio # Matches "Ok, I'm transferring to supervisor now"
      preprocess: True

    # Example 3: Weighted Ratio (often robust)
    - target: Is there anything else?
      threshold: 80
      scorer: WRatio
      preprocess: True
```

## 4. Graph State (`GraphState`)

The node's state will store the results of the matching process.

```python
from plexus.scores.nodes.BaseNode import BaseNode # Assuming BaseNode is the base
from pydantic import Field
from typing import List, Dict, Any

class FuzzyMatchExtractorGraphState(BaseNode.GraphState):
    match_found: bool = False # Overall result based on the targets logic
    matches: List[Dict[str, Any]] = Field(default_factory=list, description="Details of individual successful matches.")
    # Example match dict in list:
    # {'target': 'Hello there', 'threshold': 85, 'score': 88, 'matched_text': 'hello there', 'matched_indices': (5, 16)}
```

## 5. Core Logic (`get_matcher_node`)

- Create a node function (`matcher_node`).
- Implement a recursive helper function `_evaluate(item: Union[FuzzyTarget, FuzzyTargetGroup], text: str) -> Tuple[bool, List[Dict]]`:
    - **Base Case (`FuzzyTarget`):**
        - Perform normalization using `rapidfuzz.utils.default_process` on both `target` and the relevant slice of `text` if `preprocess` is True.
        - Use the specified `scorer` function (looked up from `rapidfuzz.fuzz`) via `rapidfuzz.process.extractOne` to find the best match for the (potentially preprocessed) `target` within the (potentially preprocessed) `text`.
        - If a match is found with `score >= threshold`, return `(True, [match_details_dict])` containing original target, score, matched text *from original input*, and indices.
        - Otherwise, return `(False, [])`.
    - **Recursive Step (`FuzzyTargetGroup`):**
        - Initialize `combined_result = True` for `and`, `False` for `or`.
        - Initialize `collected_matches = []`.
        - Iterate through `item` in `group.items`:
            - Call `item_result, item_matches = _evaluate(item, text)`.
            - Append `item_matches` to `collected_matches`.
            - **For `or`:** If `item_result` is `True`, set `combined_result = True` and `break` (short-circuit). Only matches found up to this point are relevant.
            - **For `and`:** If `item_result` is `False`, set `combined_result = False` and `break` (short-circuit). Collected matches are discarded. If loop completes without breaking, `combined_result` remains `True`.
        - Return `(combined_result, collected_matches if combined_result else [])`. # Only return matches if overall group succeeded
- The main `matcher_node` function:
    - Calls `overall_success, all_found_matches = _evaluate(self.parameters.targets, state.text)`.
    - Creates a new state object.
    - Updates the new state: `match_found = overall_success`, `matches = all_found_matches`.
    - Uses `self.log_state` to record the operation.
    - Returns the updated state.

## 6. `add_core_nodes` Method

```python
def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
    workflow.add_node(self.node_name, self.get_matcher_node())
    return workflow
```
The entry point and END edge will be handled by the `BaseNode.build_compiled_workflow` method.

## 7. Test Plan (`FuzzyMatchExtractor_test.py`)

- Test basic OR logic (match first, second, none, both).
- Test basic AND logic (match both, first only, second only, none).
- Test nested AND/OR combinations.
- Test threshold boundary conditions (score ==, >, < threshold).
- Test `ratio` vs. `partial_ratio` vs. other scorers yield expected results.
- Test `preprocess` True vs. False.
- Test edge cases: empty input `text`, text shorter than target, empty `targets` config (should fail validation).
- Verify `match_found` boolean output is correct for routing.
- Verify `matches` list contains the correct details (target, score, matched text, indices) for successful matches.

## 8. File Structure

- Node Implementation: `plexus/scores/nodes/FuzzyMatchExtractor.py`
- Tests: `plexus/scores/nodes/FuzzyMatchExtractor_test.py`
- This Plan: `documentation/plans/fuzzy-match-extractor.md`

## 9. Documentation

- Ensure comprehensive docstrings for the `FuzzyMatchExtractor` class, its `Parameters` (including `FuzzyTarget` and `FuzzyTargetGroup`), and the `GraphState`.
- Clearly explain the purpose of the node, how the `targets` structure works with `operator` (`and`/`or`), and the meaning of the `match_found` and `matches` state fields.
- Detail each option within `FuzzyTarget`, especially:
    - The available `scorer` values (`ratio`, `partial_ratio`, `token_sort_ratio`, `token_set_ratio`, `WRatio`, `QRatio`) and briefly what they do.
    - The behavior of the `preprocess` flag (applying `rapidfuzz.utils.default_process` for lowercase and alphanumeric filtering). 
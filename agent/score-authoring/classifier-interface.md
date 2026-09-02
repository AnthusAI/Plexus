---
id: score-authoring.classifier-interface
title: Score Interface Contract
summary: Interface contract for Plexus Score base class — Input, Result, predict(), validation, cost tracking.
namespace: score-authoring
status: canonical
disclosure: reference
audience: agent
tags: [classifier, interface, score]
related:
  - score-authoring.score-yaml-format
  - score-authoring.langgraph-score-yaml-format
---
# Score Interface Contract

All scoring in Plexus derives from the abstract `Score` base class (`plexus/scores/Score.py`). This defines the interface that every score implementation must satisfy.

## Base Class

```python
from plexus.scores.Score import Score

class MyScore(Score):
    async def predict(self, model_input: Score.Input, **kwargs) -> Union[Score.Result, List[Score.Result]]:
        ...
```

`Score` inherits from `ABC`, `ScoreData`, and `ScoreVisualization`. It uses Pydantic for all data models.

## Score.Input

Defined in `plexus/core/ScoreInput.py`. Lightweight to avoid heavy import chains.

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `text` | `str` | required | Content to classify (transcript, document, etc.) |
| `metadata` | `dict` | `{}` | Contextual data (source, timestamps, tracking IDs) |
| `results` | `Optional[List[Any]]` | `None` | Previous score results for dependency chaining |

## Score.Result

Defined in `plexus/scores/Score.py`.

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `parameters` | `Score.Parameters` | required | Config used for this classification |
| `value` | `Union[str, bool]` | required | Classification output (e.g. "Yes"/"No", class label) |
| `explanation` | `Optional[str]` | `None` | Why this result was chosen |
| `confidence` | `Optional[float]` | `None` | 0.0–1.0 confidence score |
| `start_time_seconds` | `Optional[float]` | `None` | Timestamp range in source content |
| `end_time_seconds` | `Optional[float]` | `None` | Timestamp range in source content |
| `metadata` | `dict` | `{}` | Additional classification context |
| `error` | `Optional[str]` | `None` | Error message if classification failed |
| `code` | `Optional[str]` | `None` | Error/status code |

Helper methods: `is_yes()`, `is_no()`, `__eq__` (case-insensitive comparison).

## predict()

The core abstract method. Modern implementations use this signature:

```python
async def predict(
    self,
    model_input: Score.Input,
    **kwargs: Any
) -> Union[Score.Result, List[Score.Result]]:
```

Single result for binary/multi-class classification. List of results for scores that produce multiple outputs per input.

## Score.Parameters

Configuration passed at instantiation. Key fields:

| Field | Type | Purpose |
|-------|------|---------|
| `scorecard_name` | `Optional[str]` | Parent scorecard |
| `name` | `Optional[str]` | Score name |
| `id` | `Optional[Union[str, int]]` | Score ID |
| `key` | `Optional[str]` | Score key |
| `dependencies` | `Optional[List[dict]]` | Other scores this depends on |
| `validation` | `Optional[ValidationConfig]` | Output validation rules |

## Validation

Scores can declare validation constraints on their output. Applied automatically after `predict()` returns.

```yaml
validation:
  value:
    valid_classes: ["Yes", "No", "NA"]
  explanation:
    minimum_length: 10
    maximum_length: 500
    patterns: ["\\w+"]
```

`FieldValidation` supports: `valid_classes`, `patterns` (regex list), `minimum_length`, `maximum_length`. Raises `Score.ValidationError` on failure.

## Cost Tracking

Every Score instance has `self._cost_accumulator` (a `CostAccumulator`). Implementations record costs during prediction:

```python
self._cost_accumulator.add_api_call(
    provider="openai",
    model="gpt-4o",
    prompt_tokens=150,
    completion_tokens=50,
    usd=Decimal("0.003")
)
```

Accumulator tracks: `total_usd`, `prompt_tokens`, `completion_tokens`, `cached_tokens`, `api_calls`, `duration_ms`, plus a `components` list for auditing.

## Primary Implementations

- **TactusScore** (`plexus/scores/TactusScore.py`): Executes Tactus DSL (Lua-based) code for classification. Model specified in Lua via `default_model`. High-volume, in-process execution.
- **LangGraphScore** (`plexus/scores/LangGraphScore.py`): LangChain/LangGraph-based workflows. Supports complex multi-node graphs, checkpointing, batch processing.

Both are async. Both take `Score.Input` and return `Score.Result`.

## Minimal Example

```python
class SimpleScore(Score):
    async def predict(self, model_input: Score.Input, **kwargs) -> Score.Result:
        text = model_input.text
        has_greeting = text.lower().startswith("hello")
        return Score.Result(
            parameters=self.parameters,
            value="Yes" if has_greeting else "No",
            explanation=f"Text {'starts' if has_greeting else 'does not start'} with greeting",
            confidence=1.0
        )
```

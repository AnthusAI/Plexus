# Feedback Alignment Optimizer Procedure

A Tactus-based procedure for iteratively optimizing Plexus score alignment using feedback evaluations with root-cause analysis (RCA).

## Overview

This procedure packages the core optimization loop from the `plexus-scorecard-improver` skill into a standalone, repeatable Tactus procedure that can be:
- Executed programmatically from any environment
- Integrated into software as an agentic feature
- Resumed from checkpoints after interruption
- Run with human-in-the-loop (HITL) approval gates

## How It Works

### Workflow

1. **Setup & Baseline** (Stages: `setup`, `baseline`)
   - Validates scorecard and score identifiers
   - Runs initial feedback evaluation with RCA
   - Captures baseline metrics (AC1, Accuracy, Precision, Recall)

2. **Optimization Loop** (Stage: `optimize`)
   - For each iteration:
     - Analyzer agent reviews RCA and proposes targeted changes
     - HITL approval gate (if not dry run)
     - Creates new score version with proposed changes
     - Runs feedback evaluation with fixed baseline comparison
     - Calculates metric deltas
     - Logs iteration results
     - Checks stop criteria (improvement threshold, max iterations, user request)

3. **Finalization** (Stage: `finalize`)
   - Summarizes total improvement
   - HITL gate for champion promotion (if improvement > 0)
   - Returns comprehensive results

### Stop Criteria

The optimization loop stops when:
- **Max iterations reached**: Completes configured `max_iterations`
- **Improvement plateau**: AC1 improvement below `improvement_threshold` and user chooses to stop
- **User stopped**: Stop requested via procedure control
- **Error**: Evaluation or analysis fails

## Usage

### 1. CLI Execution (Recommended)

The easiest way to run the optimizer is using the dedicated `optimize` command:

```bash
# Basic usage
plexus procedure optimize -s customer-service -c empathy

# With custom parameters
plexus procedure optimize \
  -s customer-service \
  -c empathy \
  --days 60 \
  --max-iterations 5 \
  --improvement-threshold 0.03

# Dry run (analysis only, no changes)
plexus procedure optimize -s test-sc -c test-score --dry-run

# Conservative threshold (only continue if ≥5% improvement)
plexus procedure optimize -s compliance -c safety --improvement-threshold 0.05

# JSON output
plexus procedure optimize -s sales -c dnc-check -o json
```

#### Command Options

```
Options:
  -s, --scorecard TEXT            Scorecard identifier (name, key, or ID) [required]
  -c, --score TEXT                Score identifier (name, key, or ID) [required]
  -d, --days INTEGER              Feedback window in days (default: 90)
  --max-iterations INTEGER        Maximum optimization iterations (default: 10)
  --improvement-threshold FLOAT   Minimum AC1 improvement to continue (default: 0.02)
  --dry-run                       Run analysis only without making score updates
  -o, --output [json|yaml|table]  Output format (default: table)
```

### 1b. CLI Execution (Direct YAML)

You can also run directly from the YAML file:

```bash
# Run from YAML (more flexible)
plexus procedure run --yaml plexus/procedures/feedback_alignment_optimizer.yaml

# Note: When using --yaml, you need to pass params via the procedure's param mechanism
# The optimize command above is more convenient for typical use cases
```

### 2. Programmatic API

```python
from plexus.agentic import AlignmentOptimizer
from plexus.dashboard.api.client import PlexusDashboardClient

# Initialize
client = PlexusDashboardClient(api_key="your-api-key")
mcp_server = ...  # Your MCP server instance

optimizer = AlignmentOptimizer(client, mcp_server)

# Run optimization
result = await optimizer.optimize(
    scorecard="customer-service",
    score="empathy",
    days=90,
    max_iterations=10,
    improvement_threshold=0.02
)

# Access results
print(f"Success: {result['success']}")
print(f"Status: {result['status']}")
print(f"Total AC1 improvement: {result['improvement']:.4f}")
print(f"Iterations: {len(result['iterations'])}")

# Iterate through results
for iteration in result['iterations']:
    print(f"Iteration {iteration['iteration']}: {iteration['hypothesis']}")
    print(f"  AC1 delta: {iteration['deltas']['alignment']:+.4f}")
```

### 3. With Monitoring

```python
from plexus.agentic import AlignmentOptimizer, OptimizationMonitor

monitor = OptimizationMonitor()

result = await optimizer.optimize(
    scorecard="customer-service",
    score="empathy",
    days=90,
    on_iteration=monitor.on_iteration  # Real-time progress callback
)

# Print summary
monitor.print_summary()
```

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `scorecard` | string | Yes | - | Scorecard identifier (name, key, or ID) |
| `score` | string | Yes | - | Score identifier (name, key, or ID) |
| `days` | number | No | 90 | Feedback window in days for evaluation dataset |
| `max_iterations` | number | No | 10 | Maximum number of optimization iterations |
| `improvement_threshold` | number | No | 0.02 | Minimum AC1 improvement to continue (0.02 = 2%) |
| `dry_run` | boolean | No | false | If true, run analysis only without making score updates |

## Outputs

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether optimization completed successfully |
| `status` | string | Completion status: `converged`, `max_iterations`, `user_stopped`, `improvement_plateau`, or `error` |
| `message` | string | Human-readable summary message |
| `baseline_evaluation_id` | string | Initial baseline evaluation ID |
| `final_evaluation_id` | string | Final evaluation ID after optimization |
| `iterations` | array | Array of iteration results with metrics and deltas |
| `improvement` | number | Total AC1 improvement from baseline to final |
| `scorecard_id` | string | Resolved scorecard ID |
| `score_id` | string | Resolved score ID |

### Iteration Object Structure

Each iteration in the `iterations` array contains:

```json
{
  "iteration": 1,
  "score_version_id": "version-id",
  "evaluation_id": "eval-id",
  "hypothesis": "Description of expected improvement",
  "changes": "Detailed description of changes",
  "rationale": "Why this change should improve alignment",
  "metrics": {
    "alignment": 0.85,
    "accuracy": 0.90,
    "precision": 0.88,
    "recall": 0.92
  },
  "deltas": {
    "alignment": 0.03,
    "accuracy": 0.02,
    "precision": 0.01,
    "recall": 0.04
  },
  "rca_summary": {
    "topic_count": 5
  }
}
```

## Agents

### Analyzer Agent
- **Role**: Analyzes RCA output and proposes configuration improvements
- **Tools**: `plexus_evaluation_info`, `plexus_score_info`, `plexus_score_pull`, `plexus_scorecard_info`
- **Output**: Calls `done()` with JSON containing hypothesis, changes, new_code, and rationale

### Validator Agent
- **Role**: Reviews proposed changes and spot-checks predictions
- **Tools**: `plexus_predict`, `plexus_item_last`
- **Output**: Calls `done()` with JSON containing approved flag and feedback

## Human-in-the-Loop Gates

### 1. Iteration Approval
- **When**: Before applying each proposed change (unless dry_run)
- **Context**: Hypothesis, changes, rationale, current metrics, code preview
- **Decision**: Approve or reject iteration

### 2. Continue After Plateau
- **When**: AC1 improvement falls below `improvement_threshold`
- **Options**: Continue or stop
- **Decision**: Whether to continue despite small improvement

### 3. Champion Promotion
- **When**: Optimization complete with AC1 improvement > 0 (unless dry_run)
- **Context**: Total iterations, improvement, final vs baseline metrics
- **Decision**: Whether to promote final version as champion

## Checkpoint/Resume Support

The procedure automatically checkpoints state via the Tactus storage adapter:
- State persists in `Procedure.metadata` JSON field
- Can resume from interruption with full context
- Completed iterations are not re-executed on resume

```bash
# Start optimization
plexus procedure run feedback-alignment-optimizer --params '{"scorecard": "...", "score": "..."}'

# If interrupted, resume from last checkpoint
plexus procedure resume <procedure-id>
```

## MCP Tools Used

- `plexus_scorecard_info`: Validate and resolve scorecard
- `plexus_score_info`: Validate and resolve score
- `plexus_score_pull`: Fetch current score configuration
- `plexus_score_update`: Create new score versions
- `plexus_evaluation_run`: Run feedback evaluations with RCA (synchronous mode)
- `plexus_evaluation_compare`: Calculate metric deltas (optional helper)

## Implementation Files

| File | Purpose |
|------|---------|
| [plexus/procedures/feedback_alignment_optimizer.yaml](feedback_alignment_optimizer.yaml) | Main procedure definition |
| [plexus/agentic/alignment_optimizer.py](../agentic/alignment_optimizer.py) | Programmatic Python API |
| [MCP/tools/evaluation/evaluation_comparison.py](../../MCP/tools/evaluation/evaluation_comparison.py) | Delta calculation MCP tool |
| [MCP/server.py](../../MCP/server.py) | MCP tool registration |

## Examples

### Example 1: Basic Optimization

```python
result = await optimizer.optimize(
    scorecard="customer-service",
    score="empathy",
    days=90
)

if result['success']:
    print(f"Improved AC1 by {result['improvement']:.4f} in {len(result['iterations'])} iterations")
else:
    print(f"Optimization failed: {result['message']}")
```

### Example 2: Conservative Optimization

```python
# Higher threshold, fewer iterations
result = await optimizer.optimize(
    scorecard="compliance",
    score="safety-violation",
    days=30,
    max_iterations=5,
    improvement_threshold=0.05  # Only continue if ≥5% improvement
)
```

### Example 3: Exploratory Dry Run

```python
# Analyze without making changes
result = await optimizer.optimize(
    scorecard="quality",
    score="accuracy-check",
    days=60,
    dry_run=True
)

# Review baseline RCA
baseline_iter = result['iterations'][0]
print(f"Baseline AC1: {baseline_iter['metrics']['alignment']:.4f}")
print(f"RCA topics: {baseline_iter['rca_summary']['topic_count']}")
```

## Best Practices

1. **Start with dry run**: Test the procedure on a copy or with `dry_run=True` before production
2. **Use appropriate feedback window**: 90 days is standard, but adjust based on data volume
3. **Set reasonable thresholds**: 2% improvement threshold balances iteration count with gains
4. **Monitor iterations**: Use `OptimizationMonitor` or custom callbacks to track progress
5. **Review HITL prompts**: Read approval context carefully before accepting changes
6. **Checkpoint frequently**: Long-running optimizations benefit from resume capability

## Troubleshooting

### Issue: "Scorecard not found"
- **Cause**: Invalid scorecard identifier
- **Fix**: Use exact name, key, or ID from `plexus_scorecards_list`

### Issue: "Analyzer timed out"
- **Cause**: RCA data too large or complex for agent to process
- **Fix**: Reduce `days` parameter to limit feedback dataset size

### Issue: "No iterations completed"
- **Cause**: Baseline evaluation failed or was rejected
- **Fix**: Check evaluation logs, verify feedback data exists for timeframe

### Issue: "AC1 regressed"
- **Cause**: Proposed change made alignment worse
- **Fix**: Review agent's rationale, consider reverting to previous version

## Future Enhancements

Potential improvements for future versions:

- **Auto-revert on regression**: Automatically revert if AC1 drops
- **Multi-score optimization**: Optimize multiple scores in parallel
- **A/B testing integration**: Support holdout set evaluations
- **Notification webhooks**: Alert external systems on completion
- **Dashboard visualization**: Real-time progress tracking UI
- **Validation set scoring**: Test changes on held-out data before applying

## Related Documentation

- [Plexus Procedures DSL Specification](DSL_SPECIFICATION.md)
- [Plexus Scorecard Improver Skill](../skills/plexus-scorecard-improver/SKILL.md)
- [Feedback Analysis Guide](https://docs.plexus.ai/feedback-alignment)
- [Score YAML Format](https://docs.plexus.ai/score-yaml-format)

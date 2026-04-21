# Feedback Alignment Optimizer — Procedure Reference

This document is for AI agents who trigger, monitor, review, continue, or branch
optimizer procedure runs. For the optimizer agent's own change-strategy reference,
see `optimizer-cookbook`.

---

## Quick Start

### Triggering a Run

**CLI:**
```bash
plexus procedure run -y plexus/procedures/feedback_alignment_optimizer.yaml \
  -s scorecard="<scorecard name>" \
  -s score="<score name>" \
  -s max_iterations=10 \
  -s max_samples=200 \
  -s days=730
```

**MCP (via `plexus_procedure_run`):**
```json
{
  "yaml_path": "plexus/procedures/feedback_alignment_optimizer.yaml",
  "params": {
    "scorecard": "<scorecard name>",
    "score": "<score name>",
    "max_iterations": 10,
    "max_samples": 200,
    "days": 730
  }
}
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `scorecard` | required | Scorecard name (exact match) |
| `score` | required | Score name (exact match) |
| `days` | 90 | Feedback lookback window in days |
| `max_iterations` | 3 | Maximum optimization cycles |
| `max_samples` | 200 | Max feedback items per evaluation |
| `improvement_threshold` | 0.02 | Min per-cycle improvement before plateau detection |
| `target_accuracy` | 0.95 | Stop early if AC1 reaches this |
| `num_candidates` | 3 | Hypothesis slots per cycle (scales down on failure) |
| `dry_run` | false | If true, never promotes champion |
| `prior_run_prescription` | "" | Inject learnings from a prior run's prescription |
| `hint` | "" | Expert guidance injected into planning context |
| `context_window` | 180000 | Token budget for agent context |

### Monitoring Progress

Use `plexus_task_info` or `plexus_procedure_info` to check status.
The procedure emits NOTIFICATION-class chat messages at key milestones:
- Cycle start/end
- Hypothesis submission results
- Evaluation outcomes
- Accept/reject decisions

### Completion Statuses

| Status | Meaning |
|--------|---------|
| `converged` | Improvement fell below threshold consistently |
| `max_iterations` | Reached cycle limit |
| `target_reached` | Hit target_accuracy AC1 |
| `user_stopped` | Human sent stop signal |
| `improvement_plateau` | 2+ consecutive stagnant cycles |
| `early_stopped` | 5+ consecutive failed cycles |
| `error` | Unrecoverable error |

---

## Architecture: The Optimization Cycle

Each run follows this structure:

### Phase A: Setup & Baseline (Fresh Runs Only)

1. **Dataset preparation** — Build or reuse a balanced evaluation dataset from the
   feedback window. Minimum 15 items required. The dataset is fixed across all cycles
   (deterministic regression testing).

2. **Champion pull** — Fetch current score configuration YAML as starting point.

3. **Baseline evaluations** — Run both:
   - **Accuracy eval**: Fixed regression dataset (same items every cycle)
   - **Feedback eval**: Latest human feedback (sampling_mode=newest, up to max_samples)

4. **Initial RCA** — Extract root cause analysis from baseline: confusion matrix,
   error categories, representative evidence items.

5. **Contradiction analysis** — Background report identifying items where human
   reviewers gave conflicting labels. Computes optimization ceiling.

### Phase 1: Planning (Per Cycle)

The agent receives a rich context injection containing:
- **Optimization history table**: All prior cycles with metrics and deltas
- **RCA context**: Confusion matrix, category hierarchies, representative transcripts
- **Contradiction landscape**: Ceiling calculation (max achievable AC1)
- **Item recurrence summary**: Cross-cycle misclassification patterns
- **Feedback landscape diagnostic**: Multi-level LLM analysis (every 2 cycles)
- **Current guidelines** (read-only) and **current config** (editable)
- **Expert hint** and **prior run prescription** (if provided)
- **Accumulated lessons**: Cross-cycle synthesized learnings

The agent then generates hypotheses sequentially, one per allocated slot.

**Slot allocation scales with failure count:**
- 0 failures: 4 slots (feedback_incremental, feedback_bold, accuracy_fix, structural)
- 2+ failures: 2 slots (feedback_incremental, accuracy_fix)
- 4+ failures: 1 slot (feedback_incremental only)

### Phase 2: Implementation (Per Hypothesis)

Each hypothesis gets a ReAct loop:
- Max 10 steps, max 10 edit retries
- Tools: `view`, `str_replace` (edit), `submit_score_version`, `done`
- After submission: smoke test on ~5 items to catch runtime crashes
- Failed smoke tests discard the version immediately

### Phase 3: Synthesis & Evaluation

All submitted versions are evaluated on both datasets.

**Success classification** (per hypothesis):
- Feedback improves >0.5% AND accuracy doesn't regress >5% → SUCCESS
- OR accuracy improves >0.5% AND feedback doesn't regress >5% → SUCCESS

**Synthesis strategies:**
- If 1+ hypotheses succeed: use best performer
- If 0 succeed: attempt "frankenstein" combination of best two
- If synthesis also fails: carry forward unchanged (or reject)

### Phase 4: Review & Acceptance

**Disqualification (hard reject):**
- Accuracy regressed >2% vs original baseline
- Feedback regressed >2% vs original baseline
- Accuracy regressed >5% vs last accepted version
- Feedback regressed >5% vs last accepted version

**Decision outcomes:**
- **ACCEPTED**: Feedback improved >0.5%
- **CARRIED**: Neutral result, version carried forward to accumulate
- **REJECTED**: Failed disqualification checks

After acceptance: State updated (baselines, RCA, item recurrence tracker).

### Convergence Checks (After Each Cycle)

- Target AC1 reached → stop
- 2 consecutive stagnant cycles → plateau stop
- 5 consecutive failed cycles → early stop
- User stop signal received → stop
- Max iterations reached → stop

### Finalize

Three LLM outputs are generated for different audiences:
- **Executive Summary** (4-6 sentences, plain English): Copy-pasteable update for anyone. What improved, main blocker, what decisions stakeholders need to make.
- **Lab Report** (technical): What happened, why it stalled, error patterns, ceiling analysis, next lab actions. Feeds `prior_run_prescription` for the next run.
- **SME Agenda** (meeting agenda format): Each item is a *decision to make* — phrased as a question with examples, options, and count of items it would resolve. For subject-matter experts who don't know what AC1 is.
- If improved and not dry_run: promote last accepted version to champion

---

## Dual Metrics System

The optimizer tracks two independent metrics simultaneously:

| Metric | Dataset | Purpose |
|--------|---------|---------|
| **Accuracy** (regression) | Fixed dataset built at baseline | Prevents regression — same items every cycle |
| **Feedback** (alignment) | Latest human feedback items | Measures real-world improvement |

Both use AC1 (agreement coefficient) as the primary metric. Acceptance requires
neither metric regresses beyond thresholds. This dual-tracking prevents "whack-a-mole"
where fixing one set of items breaks another.

---

## Continuing and Branching

### When to Continue

- Procedure stopped at max_iterations but improvement trend is still positive
- Plateau was premature (only 2 stagnant cycles, might recover)
- New hint or guidance available to try different approach

**CLI:**
```bash
plexus procedure continue <PROCEDURE_ID> --additional-cycles 5 --hint "focus on false positives"
```

**MCP:**
```json
plexus_procedure_continue(procedure_id="...", additional_cycles=5, hint="...")
```

Continuation preserves ALL accumulated state: iterations, RCA, item recurrence,
baselines, lessons learned. No re-baselining occurs.

### When to Branch

- Want to try a fundamentally different approach from an earlier cycle
- Current path hit a dead end but earlier state was promising
- Want to A/B test two different strategies from the same starting point

**CLI:**
```bash
plexus procedure branch <SOURCE_ID> --cycle 5 --additional-cycles 5 --hint "try structural changes"
```

**MCP:**
```json
plexus_procedure_branch(source_procedure_id="...", cycle=5, additional_cycles=5, hint="...")
```

Branching creates a new procedure with state truncated to the specified cycle.
The source procedure is unchanged.

---

## Interpreting Results

### Per-Cycle Data (in State.iterations array)

Each cycle record contains:
```
{
  iteration: 5,
  score_version_id: "2d0bd58b-...",
  feedback_metrics: { ac1: 0.388, accuracy: 0.72, ... },
  accuracy_metrics: { ac1: 0.388, accuracy: 0.72, ... },
  feedback_deltas: { ac1: +0.022, ... },
  accuracy_deltas: { ac1: +0.022, ... },
  accepted: true,
  done_reason: "feedback improved by 0.0220",
  exploration_results: [...],  // all hypotheses tried
  synthesis_strategy: "...",
  synthesis_reasoning: "..."
}
```

### End-of-Run Outputs

The optimizer produces three outputs at the end of each run, stored in `end_of_run_report` State:

**Executive Summary** (`end_of_run_report.executive_summary.text`)
Plain-English prose (4-6 sentences). Suitable for any audience. Covers: what improved, how many cycles, main blocker, what SME decisions are needed. No markdown.

**Lab Report** (`end_of_run_report.lab_report.text`)
Technical analysis for operators and the next optimizer run. Sections:
- **SUMMARY**: 5-7 bullets (metrics, trajectory, blocking factor, ceiling)
- **ANALYSIS**: What happened / Why it stalled / Error patterns / Ceiling
- **NEXT ACTIONS (LAB ONLY)**: Up to 5 actions under lab control (prompt, model, architecture)
- **SUSPECTED LOW-QUALITY FEEDBACK LABELS**: Specific items to review for invalidation

**SME Agenda** (`end_of_run_report.sme_agenda.text`)
Meeting agenda format for subject-matter experts. Each item is a question-to-answer (not a finding-to-read), with plain-language impact, concrete examples, and options to choose from.

### Item Recurrence Patterns

The optimizer tracks items across cycles to identify systemic issues:

| Pattern | Meaning | Action |
|---------|---------|--------|
| OSCILLATING | wrong→correct→wrong | Likely label contradiction — review label |
| PERSISTENT | Wrong in same segment 3+ cycles | Genuine policy gap or hard case |
| FLIP_FLOP | Wrong in different segments across cycles | Unstable classification boundary |
| LATE_EMERGING | First appeared cycle 3+, recurs | May be caused by earlier changes |

### Known Contradictions

Items where human reviewers gave conflicting labels for similar content.
These create an optimization ceiling — the optimizer cannot achieve AC1 higher
than what the contradiction rate allows, regardless of prompt quality.

### Feedback Landscape Diagnostic

Generated every 2 cycles (after cycle 3+). Multi-level LLM analysis:
1. **Per-item diagnoses**: Why does each tracked item resist improvement?
2. **Cross-item patterns**: Theme clustering, anti-correlated groups
3. **Temporal analysis**: Norm shift evidence, late vs early patterns
4. **Systemic diagnosis**: Feedback process issues, organizational actions needed

---

## Acting on Results

### Decision Tree

After reviewing an optimizer run's output:

**Use the Lab Report for technical next steps:**

1. **If lab report flags "review labels":**
   - Use `plexus_feedback_find` to locate flagged items
   - Review with domain expert
   - Invalidate or correct labels
   - Re-run optimizer with clean feedback

2. **If contradiction ceiling is binding:**
   - Address contradictions before running again
   - Focus on reconciling conflicting reviewer standards
   - May need reviewer calibration or guideline clarification

3. **If structural limit identified (model, input format):**
   - Consult `optimizer-cookbook` C-category changes
   - Consider DeepgramInputSource, transcript filtering, model swap
   - Branch from last good cycle to try structural approach

4. **If plateau with residual errors:**
   - Branch from best cycle, inject new hint
   - Try completely different approach direction
   - Or accept current accuracy as near-ceiling

5. **If lab report says "update guidelines":**
   - Use `plexus-score-guidelines-updater` agent
   - Incorporate findings into score guidelines
   - Then re-run optimizer with updated guidelines context

**Use the SME Agenda for stakeholder sessions:**

6. **Forward the SME Agenda** to the domain expert or team lead as a meeting agenda.
   Each item is already phrased as a decision question with examples and options.
   The output of the meeting feeds back as a `hint` or guideline update for the next run.

7. **If run succeeded and promoted champion:**
   - Verify in production via `plexus_feedback_alignment`
   - Monitor for regression over next few days
   - Use findings to inform future runs on related scores

### Cross-Run Learning

The `prior_run_prescription` parameter enables learning across runs:
```bash
plexus procedure run -y ... -s prior_run_prescription="From prior run: broad STT rescue always regresses. Focus only on narrow transcript-anchored evidence rules."
```

This injects the prior run's key findings into the planning context so the
optimizer doesn't repeat failed approaches. Use the **Lab Report** from the
previous run as the source for this parameter — it contains the technical
analysis and next-action list the optimizer needs.

---

## Thoughts on Improvement

Areas where the optimizer's meta-cognition could be enhanced:

1. **Structured lab report output**: Currently free text. Could be machine-parseable
   JSON with action type, target items, confidence, and urgency — enabling automated
   downstream workflows.

2. **Auto-chained cross-run learning**: Currently `prior_run_prescription` is manual.
   Could automatically chain: run N's lab report becomes run N+1's context without
   human intervention.

3. **Contradiction resolution workflow**: Optimizer identifies contradictions but
   doesn't trigger a human review task. Could auto-create a review queue with
   the specific items and evidence.

4. **Feedback landscape persistence**: Currently regenerated every 2 cycles within
   a run. Could persist across runs to detect long-term norm drift.

5. **Smarter plateau detection**: Current 2-cycle plateau is aggressive. Could
   differentiate "truly stuck" from "slow improvement on genuinely hard problems."

6. **Richer dashboard reporting**: The three end-of-run outputs (executive summary,
   lab report, SME agenda) are currently only in procedure state/notifications.
   Could be surfaced as first-class dashboard panels with actionable links.

7. **Hypothesis diversity tracking**: Could track which hypothesis *types* have
   been tried across cycles and runs, ensuring the optimizer explores novel
   directions rather than repeating exhausted approaches.
